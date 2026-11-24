import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from rental_service.clients.configs import ConfigsClient
from rental_service.clients.http import SourceUnavailable
from rental_service.clients.scooters import ScootersClient
from rental_service.clients.users import UserProfile, UsersClient
from rental_service.clients.zones import TariffZonesClient
from rental_service.repository.database import get_session_factory
from rental_service.repository.debts import DebtsRepository
from rental_service.repository.models import Offer
from rental_service.repository.offers import OffersRepository
from rental_service.services.pricing import calculate_prices
from rental_service.services.statuses import OfferStatus


class OfferService:
    def __init__(self) -> None:
        self.scooters = ScootersClient()
        self.zones = TariffZonesClient()
        self.users = UsersClient()
        self.configs = ConfigsClient()

    async def create_offer(self, user_id: str, scooter_id: str) -> Offer:
        # scooters критичны: SourceUnavailable улетает наверх и превращается в 503
        scooter, user, config = await asyncio.gather(
            self.scooters.get_scooter_data(scooter_id),
            self._get_user(user_id),
            self.configs.get_configs(),
        )
        zone = await self.zones.get_tariff_zone_data(scooter.zone_id, config.zone_ttl_seconds)

        async with get_session_factory().begin() as session:
            tight_mode = await DebtsRepository(session).get_system_unpaid_total() > config.system_debt_threshold
            offer = Offer(
                id=str(uuid4()),
                user_id=user_id,
                scooter_id=scooter_id,
                zone_id=scooter.zone_id,
                **calculate_prices(scooter, zone, user, config, tight_mode)._asdict(),
                status=OfferStatus.CREATED,
                created_at=datetime.now(UTC),
            )
            await OffersRepository(session).save(offer)
        return offer

    async def _get_user(self, user_id: str) -> UserProfile | None:
        try:
            return await self.users.get_user_profile(user_id)
        except SourceUnavailable:
            return None
