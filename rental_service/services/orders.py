from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rental_service.clients.configs import Config, ConfigsClient
from rental_service.clients.payments import PaymentResult, PaymentsClient
from rental_service.repository.database import get_session_factory
from rental_service.repository.debts import DebtsRepository
from rental_service.repository.models import Debt, IdempotencyKey, Order
from rental_service.repository.offers import OffersRepository
from rental_service.repository.orders import OrdersRepository
from rental_service.repository.payments import PaymentsRepository
from rental_service.services.debts import DEBT_PENALTY
from rental_service.services.errors import (
    IdempotencyKeyReused,
    LowReliability,
    OfferExpired,
    OfferNotFound,
    OfferUnavailable,
    OrderNotActive,
    OrderNotFound,
    PaymentDeclined,
    UserHasDebt,
)
from rental_service.services.statuses import DebtStatus, OfferStatus, OrderStatus, PaymentType

CANCEL_WINDOW_SECONDS = 5
PAID_RIDE_BONUS = 1


@dataclass(frozen=True)
class OrderView:
    id: str
    status: str
    current_cost: int


def ride_cost(order: Order, until: datetime) -> int:
    seconds = int((until - order.start_time).total_seconds())
    return seconds * order.price_per_minute // 60 + order.price_unlock


class OrderService:
    def __init__(self) -> None:
        self.payments = PaymentsClient()
        self.configs = ConfigsClient()

    async def start_order(self, offer_id: str) -> Order:
        config = await self.configs.get_configs()
        async with get_session_factory().begin() as session:
            order = await self._reserve(session, offer_id, config)
        if order is None:
            raise OfferExpired(offer_id)
        match order.status:
            case OrderStatus.PENDING_START:
                return await self._hold(order)
            case _:
                return order

    async def finish_order(self, order_id: str, idempotency_key: str) -> Order:
        try:
            async with get_session_factory().begin() as session:
                order, needs_clear = await self._close(session, order_id, idempotency_key)
        except IntegrityError as error:
            raise IdempotencyKeyReused(idempotency_key) from error
        if needs_clear:
            await self._clear(order, idempotency_key)
        return order

    async def get_order(self, order_id: str) -> OrderView:
        async with get_session_factory()() as session:
            order = await OrdersRepository(session).get_by_id(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        match order.status:
            case OrderStatus.ACTIVE:
                cost = ride_cost(order, datetime.now(UTC))
            case OrderStatus.PENDING_START:
                cost = 0
            case _:
                cost = order.total_amount or 0
        return OrderView(order.id, order.status, cost)

    async def _reserve(self, session: AsyncSession, offer_id: str, config: Config) -> Order | None:
        orders, offers = OrdersRepository(session), OffersRepository(session)
        if order := await orders.get_by_offer_id(offer_id):
            return order
        offer = await offers.get_by_id(offer_id)
        if offer is None:
            raise OfferNotFound(offer_id)

        now = datetime.now(UTC)
        match offer.status:
            case OfferStatus.EXPIRED:
                return None
            case OfferStatus.CREATED if now - offer.created_at > timedelta(seconds=config.offer_ttl_seconds):
                await offers.set_status(offer_id, OfferStatus.CREATED, OfferStatus.EXPIRED)
                return None
            case OfferStatus.CREATED:
                await self._check_user(session, offer.user_id, config)
                if await offers.set_status(offer_id, OfferStatus.CREATED, OfferStatus.RESERVED) is None:
                    return await self._concurrent_order(orders, offer_id)
                order = Order(
                    id=str(uuid4()),
                    offer_id=offer.id,
                    user_id=offer.user_id,
                    scooter_id=offer.scooter_id,
                    price_per_minute=offer.price_per_minute,
                    price_unlock=offer.price_unlock,
                    deposit=offer.deposit,
                    status=OrderStatus.PENDING_START,
                )
                await orders.save(order)
                return order
            case _:
                return await self._concurrent_order(orders, offer_id)

    async def _concurrent_order(self, orders: OrdersRepository, offer_id: str) -> Order:
        if order := await orders.get_by_offer_id(offer_id):
            return order
        raise OfferUnavailable(offer_id)

    async def _check_user(self, session: AsyncSession, user_id: str, config: Config) -> None:
        debts = DebtsRepository(session)
        if await debts.get_unpaid(user_id):
            raise UserHasDebt(user_id)
        tight_mode = await debts.get_system_unpaid_total() > config.system_debt_threshold
        if tight_mode and await debts.get_score(user_id) < config.min_score_in_tight_mode:
            raise LowReliability(user_id)

    async def _hold(self, order: Order) -> Order:
        payment_key = f"hold:{order.id}"
        result = await self.payments.hold_money_for_order(order.user_id, order.id, order.deposit, payment_key)
        async with get_session_factory().begin() as session:
            orders, offers = OrdersRepository(session), OffersRepository(session)
            match result:
                case PaymentResult.DECLINED:
                    if await orders.delete_pending(order.id):
                        await offers.set_status(order.offer_id, OfferStatus.RESERVED, OfferStatus.CREATED)
                case PaymentResult.UNKNOWN:
                    await PaymentsRepository(session).record(
                        payment_key, order.id, PaymentType.HOLD, result, order.deposit
                    )
                    return order
                case PaymentResult.SUCCESS:
                    await PaymentsRepository(session).record(
                        payment_key, order.id, PaymentType.HOLD, result, order.deposit
                    )
                    started = await orders.set_status(
                        order.id, OrderStatus.PENDING_START, OrderStatus.ACTIVE, start_time=datetime.now(UTC)
                    )
                    await offers.set_status(order.offer_id, OfferStatus.RESERVED, OfferStatus.USED)
                    if started := started or await orders.get_by_id(order.id):
                        return started
                    raise OrderNotFound(order.id)
        raise PaymentDeclined(order.id)

    async def _close(self, session: AsyncSession, order_id: str, idempotency_key: str) -> tuple[Order, bool]:
        orders = OrdersRepository(session)
        order = await orders.lock(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        if key := await orders.get_idempotency_key(idempotency_key):
            if key.order_id != order_id:
                raise IdempotencyKeyReused(idempotency_key)
            return order, key.result is None

        match order.status:
            case OrderStatus.PENDING_START:
                raise OrderNotActive(order_id)
            case OrderStatus.ACTIVE:
                now = datetime.now(UTC)
                cancelled = (now - order.start_time).total_seconds() < CANCEL_WINDOW_SECONDS
                closed = await orders.set_status(
                    order_id,
                    OrderStatus.ACTIVE,
                    OrderStatus.CANCELLED if cancelled else OrderStatus.FINISHED,
                    finish_time=now,
                    total_amount=0 if cancelled else ride_cost(order, now),
                )
                await orders.save_idempotency_key(
                    IdempotencyKey(key=idempotency_key, order_id=order_id, result=None, created_at=now)
                )
                return closed, True
            case _:
                return order, False

    async def _clear(self, order: Order, idempotency_key: str) -> None:
        payment_key = f"clear:{order.id}"
        result = await self.payments.clear_money_for_order(
            order.user_id, order.id, order.total_amount, payment_key
        )
        async with get_session_factory().begin() as session:
            orders, debts = OrdersRepository(session), DebtsRepository(session)
            await PaymentsRepository(session).record(
                payment_key, order.id, PaymentType.CLEAR, result, order.total_amount
            )
            if result is PaymentResult.UNKNOWN or not await orders.complete_idempotency_key(idempotency_key, result):
                return
            match result, order.status:
                case PaymentResult.SUCCESS, OrderStatus.FINISHED:
                    await debts.add_score(order.user_id, PAID_RIDE_BONUS)
                case PaymentResult.DECLINED, OrderStatus.FINISHED:
                    await debts.save(
                        Debt(
                            id=str(uuid4()),
                            user_id=order.user_id,
                            order_id=order.id,
                            amount=order.total_amount,
                            status=DebtStatus.UNPAID,
                            created_at=datetime.now(UTC),
                        )
                    )
                    await debts.add_score(order.user_id, DEBT_PENALTY)
