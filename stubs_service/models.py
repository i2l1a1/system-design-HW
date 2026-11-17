from dataclasses import dataclass


@dataclass
class ScooterData:
    id: str
    zone_id: str
    charge: int


@dataclass
class TariffZone:
    id: str
    price_per_minute: int
    price_unlock: int
    default_deposit: int


@dataclass
class UserProfile:
    id: str
    has_subscription: bool
    trusted: bool
