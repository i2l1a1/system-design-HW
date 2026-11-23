from typing import NamedTuple

from rental_service.clients.configs import Config
from rental_service.clients.scooters import ScooterData
from rental_service.clients.users import UserProfile
from rental_service.clients.zones import TariffZone

# ниже такого заряда даём скидку (MAGIC_CONSTANT из исходного main.py)
LOW_CHARGE = 28


class Prices(NamedTuple):
    price_per_minute: int
    price_unlock: int
    deposit: int


def calculate_prices(
    scooter: ScooterData,
    zone: TariffZone,
    user: UserProfile | None,
    config: Config,
    tight_mode: bool,
) -> Prices:
    price_per_minute = int(zone.price_per_minute * config.surge)
    if scooter.charge < LOW_CHARGE:
        price_per_minute = int(price_per_minute * config.low_charge_discount)

    if user is None:
        return Prices(int(price_per_minute * config.antifraud_coeff), zone.price_unlock, zone.default_deposit)

    return Prices(
        price_per_minute=price_per_minute,
        price_unlock=0 if user.has_subscription else zone.price_unlock,
        deposit=zone.default_deposit if tight_mode or not user.trusted else 0,
    )
