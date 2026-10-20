"""What a Lace puts under its reply: choices the founder can click, and cards
drawn only from what it has saved or a search suggested."""

import json

from agents.lace.cards import account_card, draft_card
from agents.lace.tools import build_tools
from agents.schemas.lace import AccountSummary, CompetitorSummary, DraftSummary, Suggestions


def _tools(store, settings):
    return {t.name: t for t in build_tools(store, settings)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


async def test_choices_are_offered_within_limits(store, settings):
    ask = _tools(store, settings)["ask_choice"]
    result = await _run(ask, question="Which market first?", options=["Kenya", " Nigeria ", ""])
    assert result["ok"] and result["data"]["ui"] == [
        {"type": "choices", "question": "Which market first?", "options": ["Kenya", "Nigeria"]}]
    assert not (await _run(ask, question="Pick", options=["Only one"]))["ok"]
    assert not (await _run(ask, question="Pick", options=["a", "b", "c", "d", "e", "f"]))["ok"]
    assert not (await _run(ask, question="Pick", options=["x" * 61, "b"]))["ok"]


async def test_show_draws_cards_from_saved_items_only(store, settings):
    store.tracked = [CompetitorSummary(id="c1", name="Rival", website="https://rival.test", summary="Payroll for vets.",
                                       origin="found", status="tracked")]
    show = _tools(store, settings)["show"]
    result = await _run(show, kind="competitor", ids=["c1", "c-made-up"])
    assert result["ok"] and "Not found: c-made-up" in result["summary"]
    assert result["data"]["ui"] == [{"type": "card", "kind": "competitor", "id": "c1", "title": "Rival",
                                     "subtitle": "https://rival.test", "body": "Payroll for vets.",
                                     "url": "https://rival.test"}]
    assert not (await _run(show, kind="competitor", ids=["nope"]))["ok"]
    assert not (await _run(show, kind="account", ids=[f"a{i}" for i in range(7)]))["ok"]


def test_cards_say_what_the_item_says():
    account = AccountSummary(id="a1", name="SunCulture", account_type="company", website="https://sunculture.test",
                             geo="Kenya", trigger="Raised a Series B", need="Fleet tracking", fit_strength="strong",
                             capability="Live fuel telemetry", payoff="8% lower fuel spend")
    card = account_card(account)
    assert (card.subtitle, card.body) == ("Kenya · strong fit", "Why now: Raised a Series B. Their need: Fleet tracking. "
                                          "How we help: Live fuel telemetry. Payoff: 8% lower fuel spend")
    draft = draft_card(DraftSummary(id="d1", channel="email", recipient="Amina", company="SunCulture",
                                    subject="Fleet costs", body="Hi " + "x" * 400))
    assert draft.title == "To Amina at SunCulture" and draft.subtitle == "email · Fleet costs"
    assert draft.body.endswith("…") and len(draft.body) <= 281


async def test_list_suggestions_says_what_waits(store, settings):
    tools = _tools(store, settings)
    assert (await _run(tools["list_suggestions"]))["summary"] == "Nothing is waiting for the founder to review."
    store.suggested = Suggestions(competitors=[CompetitorSummary(id="c9", name="New Rival", website="https://n.test",
                                                                 origin="found", status="suggested")])
    result = await _run(tools["list_suggestions"])
    assert result["summary"].startswith("1 competitors, 0 accounts and 0 opportunities")
    shown = await _run(tools["show"], kind="competitor", ids=["c9"])
    assert shown["ok"] and shown["data"]["ui"][0]["title"] == "New Rival"
