import time
from collections import OrderedDict
from dataclasses import dataclass

from pydantic import BaseModel

from rental_service.clients.http import SourceUnavailable, get_model

CACHE_SIZE = 1024
RETRY_SECONDS = 5


class TariffZone(BaseModel):
    id: str
    price_per_minute: int
    price_unlock: int
    default_deposit: int


@dataclass
class _Entry:
    zone: TariffZone
    fresh_until: float


class TariffZonesClient:
    _cache: OrderedDict[str, _Entry] = OrderedDict()

    async def get_tariff_zone_data(self, zone_id: str, ttl_seconds: float = 600) -> TariffZone:
        cache = type(self)._cache
        entry = cache.get(zone_id)
        if entry is not None:
            cache.move_to_end(zone_id)
            if time.monotonic() < entry.fresh_until:
                return entry.zone
        try:
            zone = await get_model(TariffZone, "/tariff-zone-data", id=zone_id)
        except SourceUnavailable:
            if entry is None:
                raise
            entry.fresh_until = time.monotonic() + RETRY_SECONDS
            return entry.zone
        cache[zone_id] = _Entry(zone, time.monotonic() + ttl_seconds)
        cache.move_to_end(zone_id)
        while len(cache) > CACHE_SIZE:
            cache.popitem(last=False)
        return zone
