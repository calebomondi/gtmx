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
