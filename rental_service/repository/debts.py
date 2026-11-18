from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.repository.models import Debt, UserReliability


class DebtsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, debt: Debt) -> None:
        raise NotImplementedError

    async def get_by_id(self, debt_id: str) -> Debt | None:
        raise NotImplementedError

    async def update(self, debt: Debt) -> None:
        raise NotImplementedError

    async def save_reliability(self, reliability: UserReliability) -> None:
        raise NotImplementedError

    async def get_reliability(self, user_id: str) -> UserReliability | None:
        raise NotImplementedError

    async def update_reliability(self, reliability: UserReliability) -> None:
        raise NotImplementedError
