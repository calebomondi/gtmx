"""Usage records for paid external APIs (Exa, Bright Data), so the admin
dashboard can show what each run and day cost. data_sources only reports; the
backend registers the sink that persists, keeping lower layers free of the
database."""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from utils.log import logger

_sink: Callable[[dict], None] | None = None


def set_sink(sink: Callable[[dict], None] | None) -> None:
    global _sink
    _sink = sink


@contextmanager
def track(provider: str, operation: str) -> Iterator[None]:
    """Record one paid call; a call that raises is recorded as failed (it may
    still be billed) and the exception propagates unchanged."""
    started, ok = time.monotonic(), False
    try:
        yield
        ok = True
    finally:
        if _sink is not None:
            try:
                _sink({"provider": provider, "operation": operation[:64], "ok": ok,
                       "seconds": round(time.monotonic() - started, 3)})
            except Exception:  # noqa: BLE001 -- accounting must never break the call
                logger.exception("API usage sink failed")
