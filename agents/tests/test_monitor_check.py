"""Monitoring compares sources, not summaries: an unchanged site and no new
news, events or posts means no changes and no LLM call. The first check
reports only what is notable from the last month."""

import pytest

from agents.pipelines.monitor import check_competitor as cc
from agents.schemas.monitor import ChangeReport, CompetitorChange


@pytest.fixture
def web(monkeypatch):
    page = {"text": "Pro plan  $10/seat", "news": [], "events": []}
    monkeypatch.setattr(cc, "scrape_url", lambda url, cfg: page["text"])
    monkeypatch.setattr(cc, "search_and_scrape", lambda query, *a, **k: page["events"] if "webinar" in query else page["news"])
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
    state, _ = cc.check("Rival", "https://rival.example", None, "Us")
    page["news"] = [{"url": "https://n/1", "title": "Old", "text": ""}]
    state, _ = cc.check("Rival", "https://rival.example", state, "Us")
    llm_calls.clear()
    page["text"] = ""  # site down this time
    _, changes = cc.check("Rival", "https://rival.example", state, "Us")
    assert changes == [] and llm_calls == []  # same news, site blip ignored
    page["news"] = [{"url": "https://n/1", "title": "Old", "text": ""}, {"url": "https://n/2", "title": "Raised $20M", "text": ""}]
    cc.check("Rival", "https://rival.example", state, "Us")
    assert len(llm_calls) == 1 and "Raised $20M" in llm_calls[0]["messages"][0].content and "Old" not in llm_calls[0]["messages"][0].content.split("NEW NEWS")[1]


def test_first_check_reports_whats_recent(web):
    page, llm_calls = web
    page["events"] = [{"url": "https://e/1", "title": "Rival at AI Summit Nairobi", "text": ""}]
    posts = [{"platform": "linkedin", "url": "https://li/p/1", "text": "Launching Rival 2.0", "date": "2026-10-10"}]
    state, changes = cc.check("Rival", "https://rival.example", None, "Us", posts=posts)
    prompt = llm_calls[0]["messages"][0].content
    assert llm_calls[0]["log_label"] == "monitor_first_check" and "AI Summit Nairobi" in prompt and "Rival 2.0" in prompt
    assert len(changes) == 1 and state["post_urls"] == ["https://li/p/1"]


def test_new_social_posts_are_compared_but_seen_ones_are_not(web):
    page, llm_calls = web
    post = {"platform": "x", "url": "https://x/1", "text": "Price drop!", "date": "2026-10-11"}
    state, _ = cc.check("Rival", "https://rival.example", None, "Us", posts=[post])
    llm_calls.clear()
    cc.check("Rival", "https://rival.example", state, "Us", posts=[post])
    assert llm_calls == []
    cc.check("Rival", "https://rival.example", state, "Us", posts=[post, {**post, "url": "https://x/2", "text": "Webinar Thursday"}])
    assert len(llm_calls) == 1 and "Webinar Thursday" in llm_calls[0]["messages"][0].content
