import time
from collections import OrderedDict

from pydantic import BaseModel

from rental_service.clients.http import SourceUnavailable, get_model

CACHE_SIZE = 1024
RETRY_SECONDS = 5


class TariffZone(BaseModel):
    id: str
    price_per_minute: int
    price_unlock: int
    default_deposit: int


class TariffZonesClient:
    _cache: OrderedDict[str, tuple[TariffZone, float]] = OrderedDict()

    async def get_tariff_zone_data(self, zone_id: str, ttl_seconds: float = 600) -> TariffZone:
        cache = type(self)._cache
        cached, fresh_until = cache.get(zone_id, (None, 0.0))
        if time.monotonic() < fresh_until:
            cache.move_to_end(zone_id)
            return cached
        try:
            zone, ttl = await get_model(TariffZone, "/tariff-zone-data", id=zone_id), ttl_seconds
        except SourceUnavailable:
            if cached is None:
                raise
            zone, ttl = cached, RETRY_SECONDS
        cache[zone_id] = (zone, time.monotonic() + ttl)
        cache.move_to_end(zone_id)
        if len(cache) > CACHE_SIZE:
            cache.popitem(last=False)
        return zone
