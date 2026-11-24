from __future__ import annotations

from datetime import datetime

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

OLD_ORDERS = text("""
    SELECT o.id, o.offer_id, (o.finish_time AT TIME ZONE 'UTC')::date AS day,
           jsonb_build_object(
               'order', to_jsonb(o),
               'offer', to_jsonb(f),
               'debts', (SELECT coalesce(jsonb_agg(d), '[]') FROM debts d WHERE d.order_id = o.id),
               'payments', (SELECT coalesce(jsonb_agg(p), '[]') FROM payment_operations p WHERE p.order_id = o.id),
               'idempotency_keys', (SELECT coalesce(jsonb_agg(k), '[]') FROM idempotency_keys k WHERE k.order_id = o.id)
           )::text AS record
    FROM orders o JOIN offers f ON f.id = o.offer_id
    WHERE o.status IN ('finished', 'cancelled') AND o.finish_time < :before
      AND NOT EXISTS (SELECT 1 FROM debts d WHERE d.order_id = o.id AND d.status = 'unpaid')
      AND NOT EXISTS (SELECT 1 FROM payment_operations p WHERE p.order_id = o.id AND p.status = 'unknown')
    ORDER BY o.finish_time LIMIT :limit
    FOR UPDATE OF o SKIP LOCKED
""")
UNUSED_OFFERS = text("""
    DELETE FROM offers WHERE id IN (
        SELECT f.id FROM offers f
        WHERE f.status IN ('created', 'expired') AND f.created_at < :before
          AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.offer_id = f.id)
        LIMIT :limit FOR UPDATE SKIP LOCKED
    )
""")
DELETES = (
    "DELETE FROM idempotency_keys WHERE order_id = ANY(:orders)",
    "DELETE FROM payment_operations WHERE order_id = ANY(:orders)",
    "DELETE FROM debts WHERE order_id = ANY(:orders)",
    "DELETE FROM orders WHERE id = ANY(:orders)",
    "DELETE FROM offers WHERE id = ANY(:offers)",
)


class ArchiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_old_orders(self, before: datetime, limit: int) -> list[Row]:
        return list(await self._session.execute(OLD_ORDERS, {"before": before, "limit": limit}))

    async def delete_orders(self, rows: list[Row]) -> None:
        ids = {"orders": [row.id for row in rows], "offers": [row.offer_id for row in rows]}
        for statement in DELETES:
            await self._session.execute(text(statement), ids)

    async def delete_unused_offers(self, before: datetime, limit: int) -> int:
        return (await self._session.execute(UNUSED_OFFERS, {"before": before, "limit": limit})).rowcount
