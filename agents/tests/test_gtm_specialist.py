"""The GTM specialist researches, plans, consults the other specialists only
when the plan asks, writes in the sender's voice, and rewrites once when the
review fails."""

import pytest

from agents.pipelines import team
from agents.pipelines.outreach import gtm_specialist as gs
from agents.schemas.outreach import AccountResearch, Consultation, DraftReview, OutreachDraft, OutreachPlan

TEAM = {
    "gtm": {"name": "Amani Njoroge", "role": "Head of Channel Partnerships", "description": "Owns outbound."},
    "competition": {"name": "Zawadi Otieno", "role": "Rival Intelligence Lead", "description": "Tracks rivals."},
    "product": {"name": "Baraka Mwangi", "role": "Principal Engineer", "description": "Knows the product."},
}


def _brief(channel="email"):
    return gs.OutreachBrief(
        channel=channel, sender_name="Wanjiku", offer="Offer: Associative memory for edge AI",
        account="Account: Acme (hiring 2 ML engineers)", contact_name="Ada Lovelace", contact_title="CTO",
        website="https://acme.example", trigger_source="https://jobs.example/acme",
        team=TEAM, research={"competition": "Rival X charges $40/seat and needs GPUs.", "product": "Runs on CPU."},
    )


GOOD_BODY = (
    "Hi Ada,\n\nAcme is hiring two ML engineers, which usually means the GPU bill is about to grow faster "
    "than the team. Teams in that spot often find that training on the CPUs they already run keeps model "
    "work moving while cloud spend stays flat, and that is exactly what our associative memory does for "
    "edge AI teams across Nairobi today.\n\nWould a 15-minute call next week be useful?\n\nWanjiku"
)


@pytest.fixture
def llm(monkeypatch):
    calls, script = [], {"consult": [], "reviews": [DraftReview(passes=True)]}
    monkeypatch.setattr(gs, "_sources", lambda brief: "[https://acme.example] Acme is hiring two ML engineers.")

    def fake(messages, schema=None, **kw):
        label = kw["log_label"]
        calls.append((label, messages[0].content))
        if schema is AccountResearch:
            return AccountResearch(what_they_do="Payments for SMEs", facts=[{"fact": "Hiring 2 ML engineers", "source": "https://jobs.example/acme"}])
        if schema is OutreachPlan:
            return OutreachPlan(hook_fact="Hiring 2 ML engineers", problem="GPU costs", outcome="Train on CPUs",
                                ask="15-minute call?", consult=script["consult"])
        if schema is OutreachDraft:
            return OutreachDraft(subject="Your ML hires", body=GOOD_BODY)
        if schema is DraftReview:
            return script["reviews"].pop(0)
        return "Rival X needs GPUs; we don't."  # a consultation (plain text)
    monkeypatch.setattr(gs, "invoke_structured_with_fallback", fake)
    monkeypatch.setattr(team, "invoke_structured_with_fallback", fake)
    return calls, script


def test_writes_from_research_without_consulting_when_not_needed(llm):
    calls, _ = llm
    draft = gs.write_first_touch(_brief(), "Cloud of Association")
    assert [label for label, _ in calls] == ["outreach_research", "outreach_plan", "outreach_write:email", "outreach_review"]
    assert "Amani Njoroge" in calls[1][1] and "hiring two ML engineers" in calls[0][1]
    assert 'signed "Wanjiku"' in calls[2][1] and draft.subject == "Your ML hires"


def test_consults_the_named_specialist_from_their_own_research(llm):
    calls, script = llm
    script["consult"] = [Consultation(domain="competition", question="How do we beat Rival X?")]
    gs.write_first_touch(_brief(), "Cloud of Association")
    consult = next(prompt for label, prompt in calls if label == "outreach_consult:competition")
    assert "Zawadi Otieno" in consult and "Rival X charges $40/seat" in consult
    write = next(prompt for label, prompt in calls if label.startswith("outreach_write"))
    assert "Rival X needs GPUs; we don't." in write


def test_a_failed_review_gets_one_rewrite_with_the_feedback(llm):
    calls, script = llm
    script["reviews"] = [DraftReview(passes=False, problems=["Opening is generic"])]
    gs.write_first_touch(_brief(), "Cloud of Association")
    writes = [prompt for label, prompt in calls if label.startswith("outreach_write")]
    assert len(writes) == 2 and "Opening is generic" in writes[1]


def test_linkedin_drafts_have_no_subject(llm):
    assert gs.write_first_touch(_brief("linkedin"), "Cloud of Association").subject == ""


def test_lint_catches_what_a_lenient_reviewer_misses():
    bad = OutreachDraft(subject="Unlock synergy", body="Hope you're well! We're aware that your team struggles. Call?")
    problems = gs.lint(_brief(), bad)
    assert any("synergy" in p for p in problems) and any("greeting" in p for p in problems)
    assert any("exclamation" in p for p in problems) and any("Wanjiku" in p for p in problems)
    assert gs.lint(_brief(), OutreachDraft(subject="Your ML hires", body=GOOD_BODY)) == []


def test_lint_failures_force_a_rewrite_even_when_the_review_passes(llm, monkeypatch):
    calls, _ = llm
    monkeypatch.setattr(gs, "lint", lambda brief, draft, sources=None: ["Remove \"enhance\""])
    gs.write_first_touch(_brief(), "Cloud of Association")
    writes = [prompt for label, prompt in calls if label.startswith("outreach_write")]
    assert len(writes) == 2 and 'Remove "enhance"' in writes[1]
