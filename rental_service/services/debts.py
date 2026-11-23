from __future__ import annotations

from rental_service.repository.database import get_session_factory
from rental_service.repository.debts import DebtsRepository
from rental_service.repository.models import Debt
from rental_service.services.errors import DebtNotFound

DEBT_PENALTY = -20
REPAY_BONUS = 10


class DebtService:
    async def get_unpaid(self, user_id: str) -> list[Debt]:
        async with get_session_factory()() as session:
            return await DebtsRepository(session).get_unpaid(user_id)

    async def repay(self, debt_id: str) -> Debt:
        async with get_session_factory().begin() as session:
            debts = DebtsRepository(session)
            if debt := await debts.repay(debt_id):
                await debts.add_score(debt.user_id, REPAY_BONUS)
                return debt
            if debt := await debts.get_by_id(debt_id):
                return debt
        raise DebtNotFound(debt_id)
