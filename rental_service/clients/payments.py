from enum import StrEnum

import httpx

from rental_service.clients.http import stubs

PAYMENTS_TIMEOUT_SECONDS = 3.0


class PaymentResult(StrEnum):
    SUCCESS = "success"
    DECLINED = "declined"
    UNKNOWN = "unknown"


class PaymentsClient:
    async def hold_money_for_order(self, user_id: str, order_id: str, amount: int, payment_key: str) -> PaymentResult:
        return await _send("/hold-money-for-order", user_id, order_id, amount, payment_key)

    async def clear_money_for_order(self, user_id: str, order_id: str, amount: int, payment_key: str) -> PaymentResult:
        return await _send("/clear-money-for-order", user_id, order_id, amount, payment_key)


async def _send(path: str, user_id: str, order_id: str, amount: int, payment_key: str) -> PaymentResult:
    payload = {"payment_key": payment_key, "user_id": user_id, "order_id": order_id, "amount": amount}
    try:
        response = await stubs.post(path, json=payload, timeout=PAYMENTS_TIMEOUT_SECONDS)
        response.raise_for_status()
        return PaymentResult(response.json()["status"])
    except httpx.HTTPStatusError as error:
        # 4xx - мы сами прислали кривой запрос, ретраить его бессмысленно
        if error.response.is_client_error:
            raise
        return PaymentResult.UNKNOWN
    except (httpx.RequestError, ValueError, KeyError, TypeError):
        # таймаут, обрыв или непонятный ответ: деньги могли и списаться, поэтому это не отказ
        return PaymentResult.UNKNOWN
