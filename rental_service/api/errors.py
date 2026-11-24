from fastapi import Request
from fastapi.responses import JSONResponse

from rental_service.services.errors import DomainError, Expired, Forbidden, NotFound, PaymentDeclined


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    match exc:
        case NotFound():
            status = 404
        case Expired():
            status = 410
        case PaymentDeclined():
            status = 402
        case Forbidden():
            status = 403
        case _:
            status = 409
    return JSONResponse(status_code=status, content={"detail": str(exc)})
