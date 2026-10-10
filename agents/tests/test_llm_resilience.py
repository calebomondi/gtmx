"""The LLM ladder falls back to the second provider, and every call attempt
(failed ones too) is reported to the usage sink, billed to the current run
even from a worker thread."""

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agents.concurrency import ContextThreadPoolExecutor
from agents.llm import main as llm


class Answer(BaseModel):
    ok: bool


class QuotaExhausted(Exception):
    pass


class FakeModel:
    def __init__(self, provider):
        self.provider = provider

    def with_structured_output(self, schema, **kw):
        return self

    def invoke(self, messages, config=None):
        if self.provider == "qwen":
            raise QuotaExhausted("Error code: 403 - insufficient_quota: Free quota exhausted")
        for handler in (config or {}).get("callbacks", []):
            handler.usage_metadata = {"m": {"input_tokens": 12, "output_tokens": 3}}
        return Answer(ok=True)


@pytest.fixture
def ladder(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_llm", lambda provider, **kw: FakeModel(provider))
    monkeypatch.setattr(llm, "_DOWN_MODELS", set())
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    llm.set_usage_sink(calls.append)
    yield calls
    llm.set_usage_sink(None)


def test_falls_back_to_second_provider_and_bills_the_run(ladder):
    token = llm.current_run_id.set("run-123")
    try:
        result = llm.invoke_structured_with_fallback(
            messages=[HumanMessage(content="hi")], schema=Answer, log_label="probe",
            providers=[("qwen", ["qwen-x"]), ("openrouter", ["fallback-y"])],
        )
    finally:
        llm.current_run_id.reset(token)
    assert result == Answer(ok=True)
    assert [(c["provider"], c["ok"]) for c in ladder] == [("qwen", False), ("openrouter", True)]
    assert all(c["run_id"] == "run-123" for c in ladder)
    assert (ladder[-1]["input_tokens"], ladder[-1]["output_tokens"]) == (12, 3)


def test_run_id_survives_worker_threads(ladder):
    token = llm.current_run_id.set("run-456")
    try:
        with ContextThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: llm.invoke_structured_with_fallback(
                messages=[HumanMessage(content="hi")], schema=Answer, log_label="threaded",
                providers=[("openrouter", ["fallback-y"])],
            ), range(2)))
    finally:
        llm.current_run_id.reset(token)
    assert [c["run_id"] for c in ladder] == ["run-456", "run-456"]


def test_default_ladder_includes_fallback_when_keyed(monkeypatch):
    monkeypatch.setattr(llm.cfg, "openai_api_key", "k")
    assert [p for p, _ in llm.default_providers()] == ["qwen", "openrouter"]
    monkeypatch.setattr(llm.cfg, "openai_api_key", "")
    assert [p for p, _ in llm.default_providers()] == ["qwen"]


def test_unknown_provider_is_an_error():
    with pytest.raises(ValueError):
        llm._llm("nope")
