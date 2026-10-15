"""Progress steps a long agent run reports while it works ("Searching: direct
substitutes", "Dropped Upwork: a marketplace, not a rival").

Agents call `report`; whoever runs them decides where steps go by setting
`current_reporter`. Like the run id in `utils.log`, it rides on a context
variable, so steps from worker threads reach the run that started them
(`agents.concurrency.ContextThreadPoolExecutor` and `asyncio.to_thread` copy
the context). With no reporter set, as in tests and notebooks, `report` does
nothing.
"""

from collections.abc import Callable
from contextvars import ContextVar

from utils.log import logger

# A step longer than this is cut: it is a status line, not a log.
MAX_STEP_CHARS = 160

current_reporter: ContextVar[Callable[[str], None] | None] = ContextVar("gtmx_progress_reporter", default=None)


def report(step: str) -> None:
    """Tell the user what the run is doing now. Never raises: a step that
    can't be delivered must not stop the work it describes."""
    reporter = current_reporter.get()
    if reporter is None or not step.strip():
        return
    text = step.strip()
    if len(text) > MAX_STEP_CHARS:
        text = text[: MAX_STEP_CHARS - 1].rstrip() + "…"
    try:
        reporter(text)
    except Exception:  # noqa: BLE001 -- see docstring
        logger.exception("Could not report progress step %r", text)
