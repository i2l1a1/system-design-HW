import asyncio
from enum import StrEnum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from stubs_service.models import ScooterData, TariffZone, UserProfile

# дольше любого таймаута клиентов в rental-service
TIMEOUT_SLEEP_SECONDS = 5


class Source(StrEnum):
    SCOOTERS = "scooters"
    ZONES = "zones"
    USERS = "users"
    CONFIGS = "configs"
    PAYMENTS = "payments"


class Mode(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    DECLINE = "decline"
    # операцию приняли и запомнили, но ответ не дошёл
    UNKNOWN = "unknown"


class PaymentStatus(StrEnum):
    SUCCESS = "success"
    DECLINED = "declined"


class MoneyRequest(BaseModel):
    payment_key: str
    user_id: str
    order_id: str
    amount: int


app = FastAPI()
modes = dict.fromkeys(Source, Mode.OK)
payments: dict[str, PaymentStatus] = {}


async def apply_mode(source: Source) -> None:
    match modes[source]:
        case Mode.ERROR:
            raise HTTPException(status_code=503, detail=f"{source} is down")
        case Mode.TIMEOUT:
            await asyncio.sleep(TIMEOUT_SLEEP_SECONDS)
            raise HTTPException(status_code=504, detail=f"{source} timed out")


@app.get("/modes")
async def get_modes():
    return modes


@app.put("/modes/{source}")
async def set_mode(source: Source, mode: Mode):
    if source != Source.PAYMENTS and mode in (Mode.DECLINE, Mode.UNKNOWN):
        raise HTTPException(status_code=400, detail=f"{mode} is only for payments")
    modes[source] = mode
    return modes


@app.get("/scooter-data")
async def get_scooter_data(id: str):
    await apply_mode(Source.SCOOTERS)
    # "low" в id - севший самокат, чтобы проверить скидку за заряд
    return ScooterData(id, "korolev", 20 if "low" in id else 57)


@app.get("/tariff-zone-data")
async def get_tariff_zone_data(id: str):
    await apply_mode(Source.ZONES)
    return TariffZone(id, price_per_minute=12, price_unlock=45, default_deposit=300)


@app.get("/user-profile")
async def get_user_profile(id: str):
    await apply_mode(Source.USERS)
    # подписку и доверие задаём через id, чтобы в тестах были разные пользователи
    return UserProfile(id, has_subscription="sub" in id, trusted="trusted" in id)


@app.get("/configs")
async def get_configs():
    await apply_mode(Source.CONFIGS)
    return {
        "surge": 2,
        "low_charge_discount": 0.75,
        "antifraud_coeff": 1.5,
        "system_debt_threshold": 100_000,
        "min_score_in_tight_mode": 70,
        "offer_ttl_seconds": 300,
        "zone_ttl_seconds": 600,
    }


async def process_payment(request: MoneyRequest):
    await apply_mode(Source.PAYMENTS)
    if request.payment_key not in payments:
        declined = modes[Source.PAYMENTS] == Mode.DECLINE
        payments[request.payment_key] = PaymentStatus.DECLINED if declined else PaymentStatus.SUCCESS
    if modes[Source.PAYMENTS] == Mode.UNKNOWN:
        await asyncio.sleep(TIMEOUT_SLEEP_SECONDS)
    return {"status": payments[request.payment_key]}


@app.post("/hold-money-for-order")
async def hold_money_for_order(request: MoneyRequest):
    return await process_payment(request)


@app.post("/clear-money-for-order")
async def clear_money_for_order(request: MoneyRequest):
    return await process_payment(request)
