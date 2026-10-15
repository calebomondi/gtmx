"""When the offer's website can't be read, intake gets something real to work
from (a working URL or the user's own description) before any research runs."""

import pytest

from agents.pipelines.discover import discover_offer as intake

STATE = {"website_url": "https://dead.example/", "offer_name": "Acme Consultancy", "follow_up": None}


@pytest.fixture
def reply(monkeypatch):
    asked = []

    def answer(text):
        def fake(payload):
            asked.append(payload)
            return text
        monkeypatch.setattr(intake, "interrupt", fake)
        return asked
    return answer


def test_a_working_url_is_scraped_again(reply):
    reply("try https://acme.example instead")
    step = intake.notify_unscrappable_url(STATE)
    assert step.goto == "scrape_website" and step.update["website_url"] == "https://acme.example"
    assert step.update["scrape_failed"] is False


def test_a_description_is_used_as_written_without_confirmation(reply):
    text = "We take hardware products from concept to mass manufacturing for East African startups."
    reply(text)
    step = intake.notify_unscrappable_url(STATE)
    assert step.goto == "proceed_to_description"
    assert step.update["offer_description"] == text and step.update["confirmed"] is True


@pytest.mark.parametrize("text", ["continue", "Acme Labs"])
def test_continue_or_a_name_is_asked_for_a_description(reply, text):
    asked = reply(text)
    step = intake.notify_unscrappable_url(STATE)
    assert step.goto == "notify_unscrappable_url" and step.update["asked_to_describe"] is True
    assert "describe Acme Consultancy" in asked[0]["question"]
    again = reply("continue")
    intake.notify_unscrappable_url({**STATE, **step.update})
    assert "won't guess" in again[-1]["question"]
