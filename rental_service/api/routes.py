from fastapi import APIRouter, Depends

from rental_service.api.schemas import (
    CreateOfferRequest,
    FinishOrderRequest,
    GetOrderResponse,
    OfferResponse,
    OrderResponse,
    StartOrderRequest,
)
from rental_service.services.offers import OfferService
from rental_service.services.orders import OrderService

router = APIRouter()


def get_offer_service() -> OfferService:
    return OfferService()


def get_order_service() -> OrderService:
    return OrderService()


@router.post("/offers", response_model=OfferResponse)
async def create_offer(
    body: CreateOfferRequest,
    service: OfferService = Depends(get_offer_service),
):
    return await service.create_offer(body.user_id, body.scooter_id)


@router.post("/orders", response_model=OrderResponse)
async def start_order(
    body: StartOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    return await service.start_order(body.offer_id)


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
