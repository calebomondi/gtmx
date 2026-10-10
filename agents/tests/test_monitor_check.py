"""Monitoring compares sources, not summaries: an unchanged site and no new
news means no changes and no LLM call."""

import pytest

from agents.pipelines.monitor import check_competitor as cc
from agents.schemas.monitor import ChangeReport, CompetitorChange


@pytest.fixture
def web(monkeypatch):
    page = {"text": "Pro plan  $10/seat", "news": []}
    monkeypatch.setattr(cc, "scrape_url", lambda url, cfg: page["text"])
    monkeypatch.setattr(cc, "search_and_scrape", lambda *a, **k: page["news"])
    llm_calls = []

    def fake_llm(**kw):
        llm_calls.append(kw)
        return ChangeReport(changes=[CompetitorChange(kind="pricing", title="Cut price", summary="s", importance="high")])
    monkeypatch.setattr(cc, "invoke_structured_with_fallback", fake_llm)
    return page, llm_calls


def test_baseline_then_unchanged_costs_nothing(web):
    page, llm_calls = web
    state, changes = cc.check("Rival", "https://rival.example", None, "Us")
    assert changes == [] and state["site_text"] == "Pro plan $10/seat"
    state2, changes2 = cc.check("Rival", "https://rival.example", state, "Us")
    assert changes2 == [] and llm_calls == [] and state2 == state


def test_real_site_change_goes_to_the_llm(web):
    page, llm_calls = web
    state, _ = cc.check("Rival", "https://rival.example", None, "Us")
    page["text"] = "Pro plan $8/seat"
    _, changes = cc.check("Rival", "https://rival.example", state, "Us")
    assert [c.title for c in changes] == ["Cut price"] and len(llm_calls) == 1


def test_only_new_news_triggers_and_unreachable_site_is_not_a_change(web):
    page, llm_calls = web
    page["news"] = [{"url": "https://n/1", "title": "Old", "text": ""}]
    state, _ = cc.check("Rival", "https://rival.example", None, "Us")
    page["text"] = ""  # site down this time
    _, changes = cc.check("Rival", "https://rival.example", state, "Us")
    assert changes == [] and llm_calls == []  # same news, site blip ignored
    page["news"] = [{"url": "https://n/1", "title": "Old", "text": ""}, {"url": "https://n/2", "title": "Raised $20M", "text": ""}]
    cc.check("Rival", "https://rival.example", state, "Us")
    assert len(llm_calls) == 1 and "Raised $20M" in llm_calls[0]["messages"][0].content and "Old" not in llm_calls[0]["messages"][0].content.split("NEW NEWS")[1]
