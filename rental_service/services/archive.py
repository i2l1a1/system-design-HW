from __future__ import annotations

import gzip
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from rental_service.clients.archive_storage import ArchiveStorage
from rental_service.repository.archive import ArchiveRepository
from rental_service.repository.database import get_session_factory

RETENTION_DAYS = 30
BATCH_SIZE = 500


class ArchiveService:
    def __init__(self, storage: ArchiveStorage, retention_days: int = RETENTION_DAYS, batch_size: int = BATCH_SIZE):
        self.storage = storage
        self.retention = timedelta(days=retention_days)
        self.batch_size = batch_size

    async def archive_batch(self) -> int:
        async with get_session_factory().begin() as session:
            repository = ArchiveRepository(session)
            rows = await repository.lock_old_orders(datetime.now(UTC) - self.retention, self.batch_size)
            records_by_day = defaultdict(list)
            for row in rows:
                records_by_day[row.day].append(row.record)
            for day, records in records_by_day.items():
                data = gzip.compress("\n".join(records).encode() + b"\n")
                await self.storage.put(f"orders/dt={day}/{uuid4()}.jsonl.gz", data)
            if rows:
                await repository.delete_orders(rows)
        return len(rows)

    async def delete_unused_offers(self) -> int:
        async with get_session_factory().begin() as session:
            return await ArchiveRepository(session).delete_unused_offers(
                datetime.now(UTC) - self.retention, self.batch_size
            )

    async def run_once(self) -> tuple[int, int]:
        archived = deleted_offers = 0
        while count := await self.archive_batch():
            archived += count
        while count := await self.delete_unused_offers():
            deleted_offers += count
        return archived, deleted_offers
