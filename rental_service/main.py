from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rental_service.api.errors import domain_error_handler
from rental_service.api.routes import router
from rental_service.clients.http import SourceUnavailable
from rental_service.repository.database import close_db, init_db
from rental_service.services.errors import DomainError


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    await close_db()


app = FastAPI(lifespan=lifespan)
app.include_router(router)
app.add_exception_handler(DomainError, domain_error_handler)


@app.exception_handler(NotImplementedError)
async def not_implemented_handler(_request: Request, _exc: NotImplementedError):
    return JSONResponse(status_code=501, content={"detail": "Not implemented"})


@app.exception_handler(SourceUnavailable)
async def source_unavailable_handler(_request: Request, exc: SourceUnavailable):
    return JSONResponse(status_code=503, content={"detail": f"{exc} is unavailable"})


@app.get("/health")
async def health():
    return {"status": "ok"}
