from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.repository.models import Offer
from rental_service.services.statuses import OfferStatus


class OffersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, offer: Offer) -> None:
        self._session.add(offer)
        await self._session.flush()

    async def get_by_id(self, offer_id: str) -> Offer | None:
        return await self._session.get(Offer, offer_id)

    async def set_status(self, offer_id: str, from_: OfferStatus, to: OfferStatus) -> Offer | None:
        # переход только из from_ одним UPDATE: из конкурентных запросов выиграет один, остальные получат None
        return await self._session.scalar(
            update(Offer)
            .where(Offer.id == offer_id, Offer.status == from_)
            .values(status=to)
            .returning(Offer)
            .execution_options(populate_existing=True)
        )
