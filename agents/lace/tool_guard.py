"""How every Lace tool reports: as a ToolResult the model reads, never an
exception that ends its turn."""

from collections.abc import Awaitable, Callable
from functools import wraps

from agents.schemas.lace import ToolResult
from utils.log import logger


def guarded(fn: Callable[..., Awaitable[ToolResult]]) -> Callable[..., Awaitable[str]]:
    """Serialise the result, and turn an unexpected exception into a failure
    the model can see, logged with the tool's name."""

    @wraps(fn)
    async def wrapper(*args, **kwargs) -> str:
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- reported to the model, logged here
            logger.exception("Lace tool %s failed", fn.__name__)
            result = ToolResult.failure(f"{fn.__name__} failed unexpectedly: {type(exc).__name__}")
        return result.model_dump_json(exclude_none=True)

    return wrapper
