"""Replies: read the intent, consult the team on what they asked, offer real
calendar slots, and skip messages that need no answer."""

import pytest

from agents.pipelines.outreach import gtm_replies as gr
from agents.pipelines import team
from agents.pipelines.outreach import gtm_specialist as gs
from agents.schemas.outreach import Consultation, ReplyAnalysis, ReplyDraft

TEAM = {"gtm": {"name": "Amani Njoroge", "role": "Head of Partnerships", "description": "Owns outbound."},
        "product": {"name": "Baraka Mwangi", "role": "Principal Engineer", "description": "Knows the product."}}


def _brief(slots=("Thu 16 Oct, 10:00-10:30 (Africa/Nairobi)",)):
    return gr.ReplyBrief(
        sender_name="Wanjiku", contact_name="Ada", offer="Offer: CPU-only associative memory",
        account="Acme", thread=[("us", "Hi Ada, ... Wanjiku"), ("them", "Does it run offline? Can we talk?")],
        team=TEAM, research={"product": "Runs fully offline on CPUs."}, free_slots=list(slots), timezone="Africa/Nairobi",
    )


@pytest.fixture
def llm(monkeypatch):
    calls, script = [], {"analysis": None, "bodies": ["Hi Ada,\n\nYes, it runs offline. Thu 10:00?\n\nWanjiku"]}

    def fake(messages, schema=None, **kw):
        calls.append((kw["log_label"], messages[0].content))
        if schema is ReplyAnalysis:
            return script["analysis"]
        if schema is ReplyDraft:
            return ReplyDraft(body=script["bodies"].pop(0) if len(script["bodies"]) > 1 else script["bodies"][0])
        return "It runs fully offline."
    monkeypatch.setattr(gr, "invoke_structured_with_fallback", fake)
    monkeypatch.setattr(gs, "invoke_structured_with_fallback", fake)
    monkeypatch.setattr(team, "invoke_structured_with_fallback", fake)
    return calls, script


def test_questions_are_answered_with_the_specialist_and_real_slots(llm):
    calls, script = llm
    script["analysis"] = ReplyAnalysis(intent="meeting_request", summary="Offline? Meet?", reply_needed=True,
                                       questions=["Does it run offline?"],
                                       consult=[Consultation(domain="product", question="Does it run offline?")])
    result = gr.draft_reply(_brief())
    labels = [label for label, _ in calls]
    assert labels == ["reply_analyze", "outreach_consult:product", "reply_write:meeting_request"]
    consult_prompt, write_prompt = calls[1][1], calls[2][1]
    assert "Baraka Mwangi" in consult_prompt and "Runs fully offline on CPUs." in consult_prompt
    assert "Thu 16 Oct, 10:00-10:30 (Africa/Nairobi)" in write_prompt and "It runs fully offline." in write_prompt
    assert result.draft.body.endswith("Wanjiku")


def test_out_of_office_gets_no_draft(llm):
    _, script = llm
    script["analysis"] = ReplyAnalysis(intent="out_of_office", summary="Away", reply_needed=False)
    assert gr.draft_reply(_brief()).draft is None


def test_an_agreed_time_is_confirmed_not_reoffered(llm):
    calls, script = llm
    script["analysis"] = ReplyAnalysis(intent="interested", summary="Thu works", reply_needed=True,
                                       agreed_time="2026-10-16T10:00:00")
    gr.draft_reply(_brief())
    assert "confirm it and say a calendar invite is on its way" in calls[-1][1]


def test_filler_forces_one_rewrite(llm):
    calls, script = llm
    script["analysis"] = ReplyAnalysis(intent="question", summary="?", reply_needed=True)
    script["bodies"] = ["Great question! We can enhance your stack.\n\nWanjiku", "Hi Ada,\n\nIt runs offline.\n\nWanjiku"]
    result = gr.draft_reply(_brief(slots=()))
    writes = [prompt for label, prompt in calls if label.startswith("reply_write")]
    assert len(writes) == 2 and "enhance" in writes[1] and result.draft.body.startswith("Hi Ada")
    assert "Ask which day and time suits them" in writes[0]
