from pydantic import BaseModel

from rental_service.clients.http import get_model


class Config(BaseModel):
    surge: float = 2
    low_charge_discount: float = 0.75
    antifraud_coeff: float = 1.5
    system_debt_threshold: int = 100_000
    min_score_in_tight_mode: int = 70
    offer_ttl_seconds: int = 300
    zone_ttl_seconds: int = 600


class ConfigsClient:
    async def get_configs(self) -> Config:
        return await get_model(Config, "/configs")
