"""Log lines and error reports carry the run and user they belong to."""

import json
import logging

from backend.app import observability
from utils import log


def _record(msg="boom"):
    record = logging.LogRecord("gtmx.nodes", logging.ERROR, __file__, 1, msg, None, None)
    log._ContextFilter().filter(record)
    return record


def test_log_records_carry_run_and_user():
    run_token, user_token = log.current_run_id.set("run-1"), log.current_user_id.set("user-1")
    try:
        entry = json.loads(log._JsonFormatter().format(_record()))
        text = log._TextFormatter("%(levelname)s %(message)s").format(_record())
    finally:
        log.current_run_id.reset(run_token)
        log.current_user_id.reset(user_token)
    assert entry["run_id"] == "run-1" and entry["user_id"] == "user-1" and entry["msg"] == "boom"
    assert text.endswith("[run_id=run-1 user_id=user-1]")


def test_untagged_lines_stay_clean():
    assert "run_id" not in json.loads(log._JsonFormatter().format(_record()))
    assert log._TextFormatter("%(message)s").format(_record()) == "boom"


def test_sentry_events_are_tagged_with_context():
    token = log.current_run_id.set("run-9")
    try:
        event = observability._tag_with_context({"tags": {"x": "y"}}, None)
    finally:
        log.current_run_id.reset(token)
    assert event["tags"] == {"x": "y", "run_id": "run-9"}
