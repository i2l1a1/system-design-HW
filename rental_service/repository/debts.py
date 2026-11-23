from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.repository.models import Debt, UserReliability
from rental_service.services.statuses import DebtStatus

MAX_SCORE = 100


class DebtsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, debt: Debt) -> None:
        self._session.add(debt)
        await self._session.flush()

    async def get_by_id(self, debt_id: str) -> Debt | None:
        return await self._session.get(Debt, debt_id)

    async def update(self, debt: Debt) -> None:
        await self._session.merge(debt)
        await self._session.flush()

    async def get_unpaid(self, user_id: str) -> list[Debt]:
        rows = await self._session.scalars(
            select(Debt).where(Debt.user_id == user_id, Debt.status == DebtStatus.UNPAID)
        )
        return list(rows)

    async def get_system_unpaid_total(self) -> int:
        return await self._session.scalar(
            select(func.coalesce(func.sum(Debt.amount), 0)).where(Debt.status == DebtStatus.UNPAID)
        )

    async def get_reliability(self, user_id: str) -> UserReliability | None:
        return await self._session.get(UserReliability, user_id)

    async def get_score(self, user_id: str) -> int:
        reliability = await self.get_reliability(user_id)
        return reliability.score if reliability else MAX_SCORE

    async def add_score(self, user_id: str, delta: int) -> int:
        new_score = func.least(MAX_SCORE, func.greatest(0, UserReliability.score + delta))
        statement = (
            insert(UserReliability)
            .values(user_id=user_id, score=max(0, min(MAX_SCORE, MAX_SCORE + delta)), updated_at=func.now())
            .on_conflict_do_update(index_elements=[UserReliability.user_id], set_={"score": new_score, "updated_at": func.now()})
            .returning(UserReliability.score)
        )
        return await self._session.scalar(statement)
