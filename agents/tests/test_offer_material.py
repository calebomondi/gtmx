"""The offer's own material tells every stage it covers one offer only."""

from agents import helpers
from agents.schemas.offer import OfferDataSnapshot


def test_material_scopes_itself_to_the_named_offer(monkeypatch):
    monkeypatch.setattr(helpers, "offer_brief", lambda name, body: body)
    block = helpers.format_offer_material(
        OfferDataSnapshot(offer_name="HeatherDB", website_url="https://aphorion.co/"),
        "HeatherDB is a database. Cloud of Associations makes AI sound human.", "product",
    )
    assert "about HeatherDB only" in block and "never attribute their features" in block


def test_lines_about_out_of_scope_offers_are_dropped():
    from agents.context_budget import strip_out_of_scope

    brief = (
        "HeatherDB is a self-organizing database that needs no GPU.\n"
        "- Cloud of Associations adds intuition beyond Chain of Thought.\n"
        "- Runs on a Raspberry Pi 5.\n"
        "Other offers on this page (out of scope): Cloud of Associations"
    )
    assert strip_out_of_scope(brief).splitlines() == [
        "HeatherDB is a self-organizing database that needs no GPU.",
        "- Runs on a Raspberry Pi 5.",
        "Other offers on this page (out of scope): Cloud of Associations",
    ]


def test_short_pages_are_condensed_too(monkeypatch):
    """aphorion.co is short enough that it used to skip the scoping condenser."""
    from agents import context_budget as cb

    calls = []
    monkeypatch.setattr(cb, "invoke_structured_with_fallback", lambda **k: calls.append(k) or "HeatherDB brief")
    monkeypatch.setattr(cb, "_cache_set", lambda *a: None)
    page = "HeatherDB is a database. " * 40 + "Cloud of Associations makes AI sound more human. " * 10
    assert cb.offer_brief("HeatherDB", page) == "HeatherDB brief" and len(calls) == 1
