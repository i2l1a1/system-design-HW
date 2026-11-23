import asyncio
import time

from pydantic import BaseModel

from rental_service.clients.http import SourceUnavailable, get_model

REFRESH_SECONDS = 60
RETRY_SECONDS = 5


class Config(BaseModel):
    surge: float = 2
    low_charge_discount: float = 0.75
    antifraud_coeff: float = 1.5
    system_debt_threshold: int = 100_000
    min_score_in_tight_mode: int = 70
    offer_ttl_seconds: int = 300
    zone_ttl_seconds: int = 600


class ConfigsClient:
    _config = Config()
    _refresh_at = 0.0
    _lock = asyncio.Lock()

    async def get_configs(self) -> Config:
        cache = type(self)
        if time.monotonic() < cache._refresh_at or cache._lock.locked():
            return cache._config
        async with cache._lock:
            try:
                cache._config = await get_model(Config, "/configs")
                cache._refresh_at = time.monotonic() + REFRESH_SECONDS
            except SourceUnavailable:
                cache._refresh_at = time.monotonic() + RETRY_SECONDS
        return cache._config
