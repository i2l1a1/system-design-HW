from fastapi import Request
from fastapi.responses import JSONResponse

from rental_service.services.errors import (
    DebtNotFound,
    DomainError,
    LowReliability,
    OfferExpired,
    OfferNotFound,
    OrderNotFound,
    PaymentDeclined,
    UserHasDebt,
)


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    match exc:
        case OfferNotFound() | OrderNotFound() | DebtNotFound():
            status = 404
        case OfferExpired():
            status = 410
        case PaymentDeclined():
            status = 402
        case UserHasDebt() | LowReliability():
            status = 403
        case _:
            status = 409
    return JSONResponse(status_code=status, content={"detail": type(exc).__name__, "id": str(exc)})
