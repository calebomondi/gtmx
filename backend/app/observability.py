"""Error reporting (Sentry) and agent tracing (LangSmith). Both are opt-in:
with no DSN / API key configured, nothing is sent anywhere."""

import os

import sentry_sdk

from config import settings
from utils.log import current_run_id, current_user_id, logger


def _tag_with_context(event, _hint):
    # Group a run's errors together, and find every error one user hit.
    tags = event.setdefault("tags", {})
    if run_id := current_run_id.get():
        tags["run_id"] = run_id
    if user_id := current_user_id.get():
        tags["user_id"] = user_id
    return event


def init() -> None:
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,  # no emails, IPs or request bodies
            before_send=_tag_with_context,
        )
        logger.info("Sentry error reporting enabled (%s)", settings.sentry_environment)
    if settings.langsmith_api_key:
        # LangChain reads these from the process environment, not from code.
        # Traces contain prompts and scraped content, which is why this is opt-in.
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        logger.info("LangSmith tracing enabled (project %s)", settings.langsmith_project)
