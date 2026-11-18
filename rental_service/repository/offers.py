from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.repository.models import Offer


class OffersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, offer: Offer) -> None:
        raise NotImplementedError

    async def get_by_id(self, offer_id: str) -> Offer | None:
        raise NotImplementedError

    async def update(self, offer: Offer) -> None:
        raise NotImplementedError
