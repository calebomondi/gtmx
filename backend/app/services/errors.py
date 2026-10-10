"""Domain errors raised by services. backend.app.main maps them to HTTP status
codes, so services stay independent of the web layer."""


class ServiceError(Exception):
    """Base class. The message is safe to show to the user."""


class NotFoundError(ServiceError):
    """The resource does not exist -- or belongs to someone else. The two are
    deliberately indistinguishable, so ids can't be probed across tenants."""


class ConflictError(ServiceError):
    """The request clashes with current state (duplicate name, non-empty project)."""


class InvalidInputError(ServiceError):
    """Input passed schema validation but breaks a business rule."""
