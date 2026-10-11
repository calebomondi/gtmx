"""Logging for every layer. Each record carries the run and user it belongs
to (from context variables the backend sets), so one run's story can be
pulled out of the logs. GTMX_LOG_FORMAT=json emits one JSON object per line
for a log shipper; the default is readable text."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

from config import settings

# The run a piece of work belongs to; also bills LLM and API usage to it.
current_run_id: ContextVar[str | None] = ContextVar("gtmx_current_run_id", default=None)
current_user_id: ContextVar[str | None] = ContextVar("gtmx_current_user_id", default=None)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = current_run_id.get()
        record.user_id = current_user_id.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("run_id", "user_id"):
            if getattr(record, key, None):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        tags = " ".join(f"{k}={getattr(record, k)}" for k in ("run_id", "user_id") if getattr(record, k, None))
        return f"{line} [{tags}]" if tags else line


def _configure() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_ContextFilter())
    handler.setFormatter(_JsonFormatter() if settings.log_format == "json"
                         else _TextFormatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.WARNING)
    # Our own loggers live under "gtmx"; third-party libraries stay at WARNING.
    logging.getLogger("gtmx").setLevel(settings.log_level.upper())


_configure()
logger = logging.getLogger("gtmx.nodes")
