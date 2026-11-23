from enum import StrEnum


class OfferStatus(StrEnum):
    CREATED = "created"
    RESERVED = "reserved"
    USED = "used"
    EXPIRED = "expired"


class OrderStatus(StrEnum):
    PENDING_START = "pending_start"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class DebtStatus(StrEnum):
    UNPAID = "unpaid"
    REPAID = "repaid"


class PaymentType(StrEnum):
    HOLD = "hold"
    CLEAR = "clear"
