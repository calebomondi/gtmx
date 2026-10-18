"""First-touch drafts for a Lace: the right recipient, the specialists'
research drawn from facts, and v1's writer briefed from the account."""

import json

from agents.lace.outreach import Recipient, draft_first_touch, recipient_for, research_by_domain
from agents.lace.tools import build_tools
from agents.schemas.accounts import AccountRecord, ContactRecord, TriggerEvent
from agents.schemas.lace import CompetitorSummary, LaceProfile
from agents.schemas.outreach import OutreachDraft
from lace_fakes import MemoryStore, RecordingJobs, make_fact

PROFILE = LaceProfile(name="Ada", website="https://shangalabs.com", startup_name="Shanga Labs")
TRIGGER = TriggerEvent(event="Raised a Series B", signal_type="funding_round", source="https://news.test/sunculture")


def _record(*contacts) -> AccountRecord:
    return AccountRecord(name="SunCulture", website="https://sunculture.com", trigger_event=TRIGGER,
                         key_contacts=list(contacts))


def test_recipient_prefers_a_named_email_then_linkedin_then_the_org_email():
    org = ContactRecord(email="info@sunculture.com")
    linkedin = ContactRecord(name="Dan Owuor", title="Head of Software", linkedin="https://linkedin.com/in/dan")
    named = ContactRecord(name="Samir Ibrahim", title="CEO", email="samir@sunculture.com")
    assert recipient_for(_record(org, linkedin, named)) == Recipient("email", "Samir Ibrahim", "CEO", "samir@sunculture.com")
    assert recipient_for(_record(org, linkedin)).channel == "linkedin"
    assert recipient_for(_record(org)) == Recipient("email", None, None, "info@sunculture.com")
    assert recipient_for(_record()) is None


def test_each_specialist_answers_from_its_own_facts():
    facts = [make_fact("1", "Builds rugged IoT hardware.", topic="offer"),
             make_fact("2", "Kenyan agri-IoT is growing.", topic="market"),
             make_fact("3", "Local rivals are small labs.", topic="competition")]
    rivals = [CompetitorSummary(id="c", name="Rival Labs", website="https://rival.test", summary="Prototyping shop",
                                origin="found", status="tracked")]
    research = research_by_domain(facts, rivals)
    assert "rugged IoT" in research["product"] and "agri-IoT" not in research["product"]
    assert "agri-IoT" in research["market"]
    assert "small labs" in research["competition"] and "Rival Labs: Prototyping shop" in research["competition"]


def test_the_writer_is_briefed_from_the_account_and_the_lace():
    seen = {}

    def write(brief, offer_name):
        seen.update(brief=brief, offer_name=offer_name)
        return OutreachDraft(subject="Your Series B", body="Hi Samir,...")

    recipient = Recipient("email", "Samir Ibrahim", "CEO", "samir@sunculture.com")
    draft = draft_first_touch(PROFILE, [make_fact("1", "Builds rugged IoT hardware.")], [], _record(), recipient,
                              "Caleb", write=write)
    brief = seen["brief"]
    assert draft.subject == "Your Series B" and seen["offer_name"] == "Shanga Labs"
    assert (brief.channel, brief.contact_name, brief.contact_title, brief.sender_name) == ("email", "Samir Ibrahim", "CEO", "Caleb")
    assert brief.trigger_source == "https://news.test/sunculture" and "Raised a Series B" in brief.account
    assert "rugged IoT" in brief.offer and brief.seller == "Shanga Labs"


async def test_draft_outreach_tool_starts_a_job(settings):
    jobs = RecordingJobs()
    tool = {t.name: t for t in build_tools(MemoryStore(), settings, jobs)}["draft_outreach"]
    out = json.loads(await tool.ainvoke({"account_ids": ["a1"]}))
    assert out["ok"] and jobs.started == [("draft_outreach", {"account_ids": ["a1"]})]


def test_with_no_one_reachable_the_organisations_own_account_is_messaged():
    record = _record().model_copy(update={"socials": {"linkedin": "https://linkedin.com/company/sunculture",
                                                       "instagram": "https://instagram.com/sunculture",
                                                       "x": "https://x.com/SunCulture"}})
    assert recipient_for(record) == Recipient("x", None, None, "https://x.com/SunCulture")
    only_linkedin = _record().model_copy(update={"socials": {"linkedin": "https://linkedin.com/company/sunculture"}})
    assert recipient_for(only_linkedin) is None  # a company page cannot be messaged


def test_every_channel_has_a_writing_rule_and_only_email_a_subject():
    from agents.pipelines.outreach import gtm_specialist
    for channel in ("email", "linkedin", "x", "instagram", "facebook", "tiktok"):
        assert channel in gtm_specialist.CHANNEL_RULES and channel in gtm_specialist._WORD_LIMITS
