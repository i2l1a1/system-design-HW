from fastapi import APIRouter, Depends, Response, status

from rental_service.api.schemas import (
    CreateOfferRequest,
    DebtResponse,
    FinishOrderRequest,
    GetOrderResponse,
    OfferResponse,
    OrderResponse,
    StartOrderRequest,
)
from rental_service.services.debts import DebtService
from rental_service.services.offers import OfferService
from rental_service.services.orders import OrderService
from rental_service.services.statuses import OrderStatus

router = APIRouter()


def get_offer_service() -> OfferService:
    return OfferService()


def get_order_service() -> OrderService:
    return OrderService()


def get_debt_service() -> DebtService:
    return DebtService()


@router.post("/offers", response_model=OfferResponse)
async def create_offer(
    body: CreateOfferRequest,
    service: OfferService = Depends(get_offer_service),
):
    return await service.create_offer(body.user_id, body.scooter_id)


@router.post("/orders", response_model=OrderResponse)
async def start_order(
    body: StartOrderRequest,
    response: Response,
    service: OrderService = Depends(get_order_service),
):
    order = await service.start_order(body.offer_id)
    if order.status == OrderStatus.PENDING_START:
        response.status_code = status.HTTP_202_ACCEPTED
    return order


@router.post("/orders/{order_id}/finish", response_model=OrderResponse)
async def finish_order(
    order_id: str,
    body: FinishOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    return await service.finish_order(order_id, body.idempotency_key)


@router.get("/orders/{order_id}", response_model=GetOrderResponse)
async def get_order(
    order_id: str,
    service: OrderService = Depends(get_order_service),
):
    return await service.get_order(order_id)


@router.get("/users/{user_id}/debts", response_model=list[DebtResponse])
async def get_unpaid_debts(
    user_id: str,
    service: DebtService = Depends(get_debt_service),
):
    return await service.get_unpaid(user_id)


@router.post("/debts/{debt_id}/repay", response_model=DebtResponse)
async def repay_debt(
    debt_id: str,
    service: DebtService = Depends(get_debt_service),
):
    return await service.repay(debt_id)
