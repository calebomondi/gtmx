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
                                fit=script.get("fit", ""), ask="15-minute call?", consult=script["consult"])
        if schema is OutreachDraft:
            return OutreachDraft(subject="Your ML hires", body=GOOD_BODY)
        if schema is DraftReview:
            return script["reviews"].pop(0) if script["reviews"] else DraftReview(passes=True)
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
    verdicts = iter([["Remove \"enhance\""], []])
    monkeypatch.setattr(gs, "lint", lambda brief, draft, sources=None, offer_name="": next(verdicts))
    gs.write_first_touch(_brief(), "Cloud of Association")
    writes = [prompt for label, prompt in calls if label.startswith("outreach_write")]
    assert len(writes) == 2 and 'Remove "enhance"' in writes[1]


def test_a_rewrite_that_keeps_the_mistake_gets_a_second_one(llm, monkeypatch):
    calls, _ = llm
    verdicts = iter([["Remove \"similar fintechs\""], ["Remove \"similar fintechs\""], []])
    monkeypatch.setattr(gs, "lint", lambda brief, draft, sources=None, offer_name="": next(verdicts))
    gs.write_first_touch(_brief(), "Cloud of Association")
    assert len([label for label, _ in calls if label.startswith("outreach_write")]) == 3


def test_venues_get_a_partnership_pitch_not_a_sales_pitch(llm):
    calls, script = llm
    brief = _brief()
    brief.account_type = "community"
    gs.write_first_touch(brief, "PocketAuthor")
    plan, write = calls[1][1], next(p for label, p in calls if label.startswith("outreach_write"))
    for prompt in (plan, write):
        assert "PARTNERSHIP pitch" in prompt and "community" in prompt and "SALES message" not in prompt
    calls.clear()
    script["reviews"] = [DraftReview(passes=True)]
    gs.write_first_touch(_brief(), "PocketAuthor")
    assert "SALES message" in calls[1][1]


def test_a_number_only_a_specialist_or_the_research_notes_state_is_not_sourced(llm, monkeypatch):
    seen = []
    monkeypatch.setattr(gs, "lint", lambda brief, draft, sources=None, offer_name="": seen.append(sources) or [])
    gs.write_first_touch(_brief(), "Cloud of Association")
    sources = seen[0]
    assert "Acme is hiring two ML engineers" in sources and "Rival X charges $40/seat" in sources
    assert "Payments for SMEs" not in sources  # the model's research notes


def test_a_claim_that_survives_every_rewrite_is_cut_before_the_draft_is_kept(llm, monkeypatch):
    _, script = llm
    stubborn = GOOD_BODY.replace("Would a 15-minute call next week be useful?",
                                 "Would a call on how other fintechs cut GPU spend be useful?")
    monkeypatch.setattr(gs, "_write", lambda *a, **k: OutreachDraft(subject="Your ML hires", body=stubborn))
    draft = gs.write_first_touch(_brief(), "Cloud of Association")
    assert "other fintechs" not in draft.body
    assert draft.body.count("?") == 1 and "15-minute call?" in draft.body and draft.body.endswith("Wanjiku")


def test_a_draft_only_about_their_news_is_sent_back_to_name_the_offer(llm, monkeypatch):
    calls, _ = llm
    news_only = ("Hi Ada,\n\nCongratulations on hiring two ML engineers this month; growing an ML team that fast "
                 "puts real pressure on infrastructure budgets and hiring plans across the board.\n\n"
                 "Would a 15-minute call next week be useful?\n\nWanjiku")
    drafts = iter([OutreachDraft(subject="Your ML hires", body=news_only), OutreachDraft(subject="Your ML hires", body=GOOD_BODY)])
    monkeypatch.setattr(gs, "_write", lambda *a, **k: next(drafts))
    assert any("Name Cloud of Association" in p for p in gs.lint(_brief(), OutreachDraft(subject="s", body=news_only),
                                                                   offer_name="Cloud of Association"))
    assert gs.write_first_touch(_brief(), "Cloud of Association").body == GOOD_BODY
    plan_prompt = next(prompt for label, prompt in calls if label == "outreach_plan")
    assert "FIT" in plan_prompt


def test_a_rewrite_for_a_missing_payoff_is_reviewed_again(llm):
    calls, script = llm
    script["reviews"] = [DraftReview(passes=False, problems=["Says what it does, not what it saves them"]),
                         DraftReview(passes=False, problems=["Still no payoff"])]
    gs.write_first_touch(_brief(), "Cloud of Association")
    reviews = [prompt for label, prompt in calls if label == "outreach_review"]
    writes = [prompt for label, prompt in calls if label.startswith("outreach_write")]
    assert len(reviews) == 3 and len(writes) == 3
    assert "Still no payoff" in writes[2]
    assert "business payoff" in reviews[0]


def test_the_plan_asks_for_the_business_payoff_not_a_feature(llm):
    calls, _ = llm
    gs.write_first_touch(_brief(), "Cloud of Association")
    plan_prompt = next(prompt for label, prompt in calls if label == "outreach_plan")
    assert "OUTCOME" in plan_prompt and "save (cost)" in plan_prompt


def test_naming_the_seller_counts_as_naming_the_offer():
    brief = _brief()
    brief.seller = "Shanga Labs"
    body = GOOD_BODY.replace("our associative memory", "Shanga Labs")
    problems = gs.lint(brief, OutreachDraft(subject="Your ML hires", body=body), offer_name="Hardware Integration")
    assert not any("Name " in p for p in problems)


def test_the_writer_is_told_the_seller_and_the_offer(llm):
    calls, _ = llm
    brief = _brief()
    brief.seller = "Shanga Labs"
    gs.write_first_touch(brief, "Hardware Integration")
    write_prompt = next(prompt for label, prompt in calls if label.startswith("outreach_write"))
    assert "Shanga Labs (Hardware Integration)" in write_prompt


def test_cutting_ungrounded_claims_never_leaves_a_draft_without_the_offer(llm, monkeypatch):
    _, script = llm
    script["fit"] = "Cloud of Association runs on the CPUs Acme already has, so the GPU bill stops growing."
    unsourced = ("Hi Ada,\n\nAcme is hiring two ML engineers.\n\nCloud of Association cuts GPU spend by 73%.\n\n"
                 "Would a 15-minute call next week be useful?\n\nWanjiku")
    monkeypatch.setattr(gs, "_write", lambda *a, **k: OutreachDraft(subject="Your ML hires", body=unsourced))
    body = gs.write_first_touch(_brief(), "Cloud of Association").body
    assert "73%" not in body
    assert script["fit"] in body
    assert body.index(script["fit"]) < body.index("15-minute call")


@pytest.mark.parametrize("body", ["Shanga Labs connects your scales", "ShangaLabs connects your scales"])
def test_a_seller_known_by_its_website_is_named_however_it_is_spaced(body):
    brief = _brief()
    brief.seller = "shangalabs.com"
    assert gs._names_offer(body, brief, "Hardware Integration")
    assert not gs._names_offer("We connect your scales", brief, "Hardware Integration")
