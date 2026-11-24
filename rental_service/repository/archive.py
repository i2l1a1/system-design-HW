from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.clients.payments import PaymentResult
from rental_service.repository.models import Debt, IdempotencyKey, Offer, Order, PaymentOperation
from rental_service.services.statuses import DebtStatus, OfferStatus, OrderStatus

CLOSED_STATUSES = (OrderStatus.FINISHED, OrderStatus.CANCELLED)


class ArchiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_old_orders(self, finished_before: datetime, limit: int) -> list[Order]:
        has_unpaid_debt = exists().where(Debt.order_id == Order.id, Debt.status == DebtStatus.UNPAID)
        has_unknown_payment = exists().where(
            PaymentOperation.order_id == Order.id, PaymentOperation.status == PaymentResult.UNKNOWN
        )
        rows = await self._session.scalars(
            select(Order)
            .where(
                Order.status.in_(CLOSED_STATUSES),
                Order.finish_time < finished_before,
                ~has_unpaid_debt,
                ~has_unknown_payment,
            )
            .order_by(Order.finish_time)
            .limit(limit)
            .with_for_update(skip_locked=True, of=Order)
        )
        return list(rows)

    async def get_offers(self, offer_ids: list[str]) -> list[Offer]:
        return list(await self._session.scalars(select(Offer).where(Offer.id.in_(offer_ids))))

    async def get_debts(self, order_ids: list[str]) -> list[Debt]:
        return list(await self._session.scalars(select(Debt).where(Debt.order_id.in_(order_ids))))

    async def get_payments(self, order_ids: list[str]) -> list[PaymentOperation]:
        return list(
            await self._session.scalars(select(PaymentOperation).where(PaymentOperation.order_id.in_(order_ids)))
        )

    async def get_idempotency_keys(self, order_ids: list[str]) -> list[IdempotencyKey]:
        return list(
            await self._session.scalars(select(IdempotencyKey).where(IdempotencyKey.order_id.in_(order_ids)))
        )

    async def delete_orders(self, order_ids: list[str], offer_ids: list[str]) -> None:
        await self._session.execute(delete(IdempotencyKey).where(IdempotencyKey.order_id.in_(order_ids)))
        await self._session.execute(delete(PaymentOperation).where(PaymentOperation.order_id.in_(order_ids)))
        await self._session.execute(delete(Debt).where(Debt.order_id.in_(order_ids)))
        await self._session.execute(delete(Order).where(Order.id.in_(order_ids)))
        await self._session.execute(delete(Offer).where(Offer.id.in_(offer_ids)))

    async def delete_unused_offers(self, created_before: datetime, limit: int) -> int:
        has_order = exists().where(Order.offer_id == Offer.id)
        ids = list(
            await self._session.scalars(
                select(Offer.id)
                .where(
                    Offer.status.in_((OfferStatus.CREATED, OfferStatus.EXPIRED)),
                    Offer.created_at < created_before,
                    ~has_order,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        if ids:
            await self._session.execute(delete(Offer).where(Offer.id.in_(ids)))
        return len(ids)
