from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.repository.models import PaymentOperation


class PaymentsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, payment_operation: PaymentOperation) -> None:
        self._session.add(payment_operation)
        await self._session.flush()

    async def get_by_payment_key(self, payment_key: str) -> PaymentOperation | None:
        return await self._session.get(PaymentOperation, payment_key)

    async def update(self, payment_operation: PaymentOperation) -> None:
        await self._session.merge(payment_operation)
        await self._session.flush()
