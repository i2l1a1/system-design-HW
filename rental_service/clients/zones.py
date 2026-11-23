from pydantic import BaseModel

from rental_service.clients.http import get_model


class TariffZone(BaseModel):
    id: str
    price_per_minute: int
    price_unlock: int
    default_deposit: int


class TariffZonesClient:
    async def get_tariff_zone_data(self, zone_id: str) -> TariffZone:
        return await get_model(TariffZone, "/tariff-zone-data", id=zone_id)
