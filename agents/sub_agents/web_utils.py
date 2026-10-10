"""Shared web-call runtime for the sub_agents family: bounded parallelism,
timeouts, and a small in-process search cache.

Why these exist: the account-discovery and get-competitors pipelines are chains
of Exa searches, Bright Data profile scrapes and page livecrawls. Every loop in
those pipelines used to run them serially, so total time was the SUM of every
network call — routinely tens of minutes. The helpers here are the mechanical
fix: run independent calls concurrently, never let one hung call block the run,
and never pay for the same query twice within a short window.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, Optional

from utils.log import logger


def timed_node(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
    """Wrap a graph node so each invocation logs its wall-clock cost."""

    def wrapper(state: dict) -> dict:
        t0 = time.perf_counter()
        try:
            return fn(state)
        finally:
            print(f"⏱ node '{fn.__name__}' took {time.perf_counter() - t0:.1f}s", flush=True)

    wrapper.__name__ = fn.__name__
    return wrapper

__all__ = [
    "run_parallel",
    "call_with_timeout",
    "search_cache_get",
    "search_cache_put",
    "timed_node",
    "SEARCH_TTL_SECONDS",
]

_TIMEOUT_POOL = ThreadPoolExecutor(max_workers=64, thread_name_prefix="web-call-timeout")

_SEARCH_CACHE: dict[tuple, tuple[float, Any]] = {}
_SEARCH_LOCK = threading.Lock()

SEARCH_TTL_SECONDS = float(os.environ.get("ACCOUNT_SEARCH_CACHE_TTL", "600"))


def run_parallel(fns: Iterable[Callable[[], Any]], workers: int = 8) -> list[Any]:
    """Run zero-arg callables on a thread pool, results aligned to input order.

    Exceptions are logged and become None for that slot rather than sinking the
    batch — the same "one dead call must not kill the run" contract the pipelines
    already use.
    """
    fns = list(fns)
    if not fns:
        return []
    if len(fns) == 1:
        try:
            return [fns[0]()]
        except Exception as e:  # noqa: BLE001
            logger.warning("parallel call failed: %s", e)
            return [None]
    workers = max(1, min(workers, len(fns)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(fn) for fn in fns]
        out = []
        for fn, fut in zip(fns, futs):
            try:
                out.append(fut.result())
            except Exception as e:  # noqa: BLE001
                logger.warning("parallel call failed: %s", e)
                out.append(None)
        return out


def call_with_timeout(
    fn: Callable[[], Any],
    timeout_s: float,
    *,
    default: Any = None,
    label: str = "",
) -> Any:
    """Run fn on the shared timeout pool, returning `default` if it overruns.

    A hung HTTP call is invisible from the caller's side; without this the whole
    pipeline waits on it. On timeout the worker thread keeps running in the
    background (Python cannot kill threads), which is harmless — the result is
    simply discarded.
    """
    future = _TIMEOUT_POOL.submit(fn)
    try:
        return future.result(timeout=timeout_s)
    except Exception as e:  # noqa: BLE001 -- timeouts land here too
        logger.warning("%s failed or timed out after %.0fs: %s", label or "call", timeout_s, e)
        return default


def search_cache_get(key: tuple) -> Optional[Any]:
    with _SEARCH_LOCK:
        hit = _SEARCH_CACHE.get(key)
        if hit and (time.monotonic() - hit[0]) < SEARCH_TTL_SECONDS:
            return hit[1]
        if hit:
            _SEARCH_CACHE.pop(key, None)
    return None


def search_cache_put(key: tuple, value: Any) -> Any:
    with _SEARCH_LOCK:
        if len(_SEARCH_CACHE) > 512:
            _SEARCH_CACHE.clear()
        _SEARCH_CACHE[key] = (time.monotonic(), value)
    return value
