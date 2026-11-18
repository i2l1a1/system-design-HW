from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.repository.models import IdempotencyKey, Order


class OrdersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, order: Order) -> None:
        raise NotImplementedError

    async def get_by_id(self, order_id: str) -> Order | None:
        raise NotImplementedError

    async def get_by_offer_id(self, offer_id: str) -> Order | None:
        raise NotImplementedError

    async def update(self, order: Order) -> None:
        raise NotImplementedError

    async def save_idempotency_key(self, idempotency_key: IdempotencyKey) -> None:
        raise NotImplementedError

    async def get_idempotency_key(self, key: str) -> IdempotencyKey | None:
        raise NotImplementedError

    async def update_idempotency_key(self, idempotency_key: IdempotencyKey) -> None:
        raise NotImplementedError
