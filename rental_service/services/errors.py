class DomainError(Exception):
    pass


class OfferNotFound(DomainError):
    pass


class OfferExpired(DomainError):
    pass


class OfferUnavailable(DomainError):
    pass


class OrderNotFound(DomainError):
    pass


class OrderNotActive(DomainError):
    pass


class UserHasDebt(DomainError):
    pass


class LowReliability(DomainError):
    pass


class PaymentDeclined(DomainError):
    pass


class IdempotencyKeyReused(DomainError):
    pass


class DebtNotFound(DomainError):
    pass
