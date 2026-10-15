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


def test_calls_per_provider_are_capped(monkeypatch):
    """Past llm_max_concurrency, calls queue instead of hitting the provider."""
    import threading
    import time as real_time

    state = {"now": 0, "peak": 0}
    lock = threading.Lock()

    class SlowModel(FakeModel):
        def invoke(self, messages, config=None):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            real_time.sleep(0.05)
            with lock:
                state["now"] -= 1
            return Answer(ok=True)

    monkeypatch.setattr(llm, "_llm", lambda provider, **kw: SlowModel(provider))
    monkeypatch.setattr(llm, "_DOWN_MODELS", set())
    monkeypatch.setattr(llm, "_PROVIDER_SLOTS", {})
    monkeypatch.setattr(llm.cfg, "llm_max_concurrency", 2)
    call = lambda _: llm.invoke_structured_with_fallback(  # noqa: E731
        [HumanMessage(content="hi")], Answer, log_label="t", providers=[("openrouter", ["m"])],
    )
    with ContextThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, range(8)))
    assert all(r.ok for r in results) and state["peak"] == 2


def test_dashscope_free_quota_wall_is_billing_not_a_missing_model():
    err = Exception("Error code: 403 - The free quota has been exhausted. To continue accessing the model on a paid basis")
    assert llm.classify_llm_error(err) == "billing"


def test_a_quick_call_on_a_thinking_only_model_gets_a_short_budget(monkeypatch):
    monkeypatch.setattr(llm.cfg, "dashscope_api_key", "test-key")  # building a client needs one; nothing is sent
    monkeypatch.setattr(llm, "_FORCE_THINKING_MODELS", {("qwen", "thinker")})
    quick = llm._llm("qwen", "thinker", thinking=False)
    assert quick.enable_thinking and quick.thinking_budget == llm.FORCED_THINKING_BUDGET
    assert quick.max_tokens == llm.MAX_OUTPUT_TOKENS
    deep = llm._llm("qwen", "thinker", thinking=True, thinking_budget=8000)
    assert deep.thinking_budget == 8000
