from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreateOfferRequest(BaseModel):
    user_id: str
    scooter_id: str


class OfferResponse(BaseModel):
    id: str
    user_id: str
    scooter_id: str
    zone_id: str
    price_per_minute: int
    price_unlock: int
    deposit: int
    status: str
    created_at: datetime


class StartOrderRequest(BaseModel):
    offer_id: str


class FinishOrderRequest(BaseModel):
    idempotency_key: str


class OrderResponse(BaseModel):
    id: str
    offer_id: str
    user_id: str
    scooter_id: str
    price_per_minute: int
    price_unlock: int
    deposit: int
    total_amount: int | None
    status: str
    start_time: datetime | None
    finish_time: datetime | None


class GetOrderResponse(BaseModel):
    id: str
    status: str
    current_cost: int
