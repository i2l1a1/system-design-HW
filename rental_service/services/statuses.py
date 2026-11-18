from enum import Enum


class OfferStatus(str, Enum):
    CREATED = "created"
    RESERVED = "reserved"
    USED = "used"
    EXPIRED = "expired"


class OrderStatus(str, Enum):
    PENDING_START = "pending_start"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"
