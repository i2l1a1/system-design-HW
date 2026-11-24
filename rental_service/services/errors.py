class DomainError(Exception):
    pass


class NotFound(DomainError):
    pass


class Expired(DomainError):
    pass


class Forbidden(DomainError):
    pass


class Conflict(DomainError):
    pass


class PaymentDeclined(DomainError):
    pass
