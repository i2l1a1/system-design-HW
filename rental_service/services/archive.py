from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import inspect

from rental_service.clients.archive_storage import ArchiveStorage
from rental_service.repository.archive import ArchiveRepository
from rental_service.repository.database import get_session_factory

RETENTION_DAYS = 30
BATCH_SIZE = 500


def _row(model) -> dict:
    values = {}
    for column in inspect(model).mapper.column_attrs:
        value = getattr(model, column.key)
        values[column.key] = value.isoformat() if isinstance(value, datetime) else value
    return values


class ArchiveService:
    def __init__(
        self,
        storage: ArchiveStorage,
        retention_days: int = RETENTION_DAYS,
        batch_size: int = BATCH_SIZE,
    ) -> None:
        self.storage = storage
        self.retention = timedelta(days=retention_days)
        self.batch_size = batch_size

    async def archive_batch(self) -> int:
        cutoff = datetime.now(UTC) - self.retention
        async with get_session_factory().begin() as session:
            repository = ArchiveRepository(session)
            orders = await repository.lock_old_orders(cutoff, self.batch_size)
            if not orders:
                return 0
            order_ids = [order.id for order in orders]
            offer_ids = [order.offer_id for order in orders]

            offers = {offer.id: offer for offer in await repository.get_offers(offer_ids)}
            related = defaultdict(lambda: {"debts": [], "payments": [], "idempotency_keys": []})
            for debt in await repository.get_debts(order_ids):
                related[debt.order_id]["debts"].append(_row(debt))
            for payment in await repository.get_payments(order_ids):
                related[payment.order_id]["payments"].append(_row(payment))
            for key in await repository.get_idempotency_keys(order_ids):
                related[key.order_id]["idempotency_keys"].append(_row(key))

            lines_by_day = defaultdict(list)
            for order in orders:
                record = {"order": _row(order), "offer": _row(offers[order.offer_id]), **related[order.id]}
                day = order.finish_time.astimezone(UTC).date().isoformat()
                lines_by_day[day].append(json.dumps(record, ensure_ascii=False))

            for day, lines in lines_by_day.items():
                data = gzip.compress(("\n".join(lines) + "\n").encode())
                await self.storage.put(f"orders/dt={day}/{uuid4()}.jsonl.gz", data)

            await repository.delete_orders(order_ids, offer_ids)
        return len(orders)

    async def delete_unused_offers(self) -> int:
        cutoff = datetime.now(UTC) - self.retention
        async with get_session_factory().begin() as session:
            return await ArchiveRepository(session).delete_unused_offers(cutoff, self.batch_size)

    async def run_once(self) -> tuple[int, int]:
        archived = deleted_offers = 0
        while count := await self.archive_batch():
            archived += count
        while count := await self.delete_unused_offers():
            deleted_offers += count
        return archived, deleted_offers
