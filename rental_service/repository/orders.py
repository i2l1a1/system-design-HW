from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.repository.models import IdempotencyKey, Order, PaymentOperation
from rental_service.services.statuses import OrderStatus


class OrdersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, order: Order) -> None:
        # второй заказ на тот же offer_id упадёт с IntegrityError (unique в схеме)
        self._session.add(order)
        await self._session.flush()

    async def get_by_id(self, order_id: str) -> Order | None:
        return await self._session.get(Order, order_id)

    async def lock(self, order_id: str) -> Order | None:
        return await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True)
        )

    async def get_by_offer_id(self, offer_id: str) -> Order | None:
        return await self._session.scalar(select(Order).where(Order.offer_id == offer_id))

    async def set_status(self, order_id: str, from_: OrderStatus, to: OrderStatus, **values) -> Order | None:
        return await self._session.scalar(
            update(Order)
            .where(Order.id == order_id, Order.status == from_)
            .values(status=to, **values)
            .returning(Order)
            .execution_options(populate_existing=True)
        )

    async def delete_pending(self, order_id: str) -> bool:
        # лочим строку, чтобы параллельный pending_start => active не проскочил между DELETE
        pending = await self._session.scalar(
            select(Order.id).where(Order.id == order_id, Order.status == OrderStatus.PENDING_START).with_for_update()
        )
        if pending is None:
            return False
        # hold мог записаться как unknown, а без него FK не даст удалить заказ
        await self._session.execute(delete(PaymentOperation).where(PaymentOperation.order_id == order_id))
        await self._session.execute(delete(Order).where(Order.id == order_id))
        return True

    async def save_idempotency_key(self, idempotency_key: IdempotencyKey) -> None:
        self._session.add(idempotency_key)
        await self._session.flush()

    async def get_idempotency_key(self, key: str) -> IdempotencyKey | None:
        return await self._session.get(IdempotencyKey, key)

    async def update_idempotency_key(self, idempotency_key: IdempotencyKey) -> None:
        await self._session.merge(idempotency_key)
        await self._session.flush()

    async def complete_idempotency_key(self, key: str, result: str) -> bool:
        completed = await self._session.scalar(
            update(IdempotencyKey)
            .where(IdempotencyKey.key == key, IdempotencyKey.result.is_(None))
            .values(result=result)
            .returning(IdempotencyKey.key)
        )
        return completed is not None
