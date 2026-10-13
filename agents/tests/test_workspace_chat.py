"""Chat: each question goes to the specialist it is about, who answers in the
first person from their own research, consulting colleagues when routed to."""

import pytest

from agents.pipelines import team
from agents.pipelines.chat import workspace_chat as wc
from agents.schemas.chat import ChatRoute, ChatSuggestions
from agents.schemas.outreach import Consultation

CONTEXT = wc.ChatContext(
    offer_name="Cloud of Association", offer="Offer: CPU-only associative memory",
    team={
        "competition": {"name": "Zawadi Otieno", "role": "Rival Intelligence Lead", "description": "Tracks rivals."},
        "market": {"name": "Kevin Mutua", "role": "Pricing Analyst", "description": "Knows buyers."},
        "gtm": {"name": "Amani Njoroge", "role": "Head of Partnerships", "description": "Owns outbound."},
    },
    research={"competition": "RunPod sells GPU hours at $0.40/h.", "market": "SMEs pay $20-50/seat.",
              "gtm": "Beachhead: Nairobi fintechs.", "product": "Runs on CPUs."},
)


@pytest.fixture
def llm(monkeypatch):
    calls, script = [], {"route": ChatRoute(lead="competition")}

    def fake(messages, schema=None, **kw):
        calls.append((kw["log_label"], messages))
        if schema is ChatRoute:
            return script["route"]
        if schema is ChatSuggestions:
            return ChatSuggestions(suggestions=["Who should we target first?", "hey", "How do we price it?", "Extra"])
        return "We'd answer text"
    monkeypatch.setattr(wc, "invoke_structured_with_fallback", fake)
    monkeypatch.setattr(team, "invoke_structured_with_fallback", fake)
    return calls, script


def test_the_lead_specialist_answers_in_the_first_person_from_their_research(llm):
    calls, _ = llm
    reply = wc.answer("How do we beat RunPod?", [("user", "hi"), ("assistant", "hello")], CONTEXT)
    assert reply.domain == "competition" and reply.content == "We'd answer text"
    assert [label for label, _ in calls] == ["chat_route", "chat_answer:competition"]
    system = calls[1][1][0].content
    assert "Zawadi Otieno" in system and "first person" in system and "RunPod sells GPU hours" in system
    assert [type(m).__name__ for m in calls[1][1][1:]] == ["HumanMessage", "AIMessage", "HumanMessage"]
    # It can't act later, so it points to where the app does it instead.
    assert "never promise to draft" in system and "Amani Njoroge drafts" in system


def test_cross_domain_questions_consult_colleagues(llm):
    calls, script = llm
    script["route"] = ChatRoute(lead="gtm", consult=[
        Consultation(domain="market", question="What do SMEs pay?"),
        Consultation(domain="gtm", question="ignored: the lead never consults itself"),
    ])
    wc.answer("How should we price our launch offer?", [], CONTEXT)
    labels = [label for label, _ in calls]
    assert labels == ["chat_route", "chat_consult:market", "chat_answer:gtm"]
    assert "Kevin Mutua" in calls[1][1][0].content and "Amani Njoroge" in calls[2][1][0].content


def test_web_search_only_when_routed_to_it(llm, monkeypatch):
    _, script = llm
    searched = []
    monkeypatch.setattr(wc, "_search", lambda q: searched.append(q) or [{"url": "https://n.example", "title": "News", "text": "x"}])
    wc.answer("Any RunPod news?", [], CONTEXT)
    assert searched == []
    script["route"] = ChatRoute(lead="competition", needs_web=True, queries=["RunPod funding 2026"])
    wc.answer("Any RunPod news?", [], CONTEXT)
    assert searched == ["RunPod funding 2026"]


def test_a_promise_or_a_third_person_answer_is_rewritten(llm):
    calls, _ = llm
    answers = iter(["HeatherDB is a database. I will draft three variations for you.", "We'd position on cost."])
    original = wc.invoke_structured_with_fallback

    def fake(messages, schema=None, **kw):
        if kw["log_label"].startswith("chat_answer"):
            calls.append((kw["log_label"], messages))
            return next(answers)
        return original(messages, schema, **kw)
    wc.invoke_structured_with_fallback = fake
    try:
        reply = wc.answer("Positioning?", [], CONTEXT)
    finally:
        wc.invoke_structured_with_fallback = original
    assert reply.content == "We'd position on cost."
    assert "I will draft" in calls[-1][1][-1].content


def test_voice_checks():
    assert wc.voice_problems("I'd start with Lagos fintechs.") == []
    assert len(wc.voice_problems("The market is large.")) == 1
    assert any("can't act" in p for p in wc.voice_problems("We should. I’ll prepare a one-pager."))


def test_claiming_work_that_never_happened_forces_a_rewrite():
    claimed = ("I have drafted a proposal in the **Reach Out tab** targeting the YC community managers.",
               "I've sent Amara the deck.", "I already scheduled the call.")
    for text in claimed:
        assert any("haven't done that" in p for p in wc.voice_problems(text)), text
    assert wc.voice_problems("I've drafted it below:\n\nHi Amara, ...") == []
    assert wc.voice_problems("I prepared this from our market research.") == []


@pytest.mark.parametrize("text", ["hi", "Hey!", "hello there", "who are you?", "Who are you guys", "thanks", "good morning"])
def test_greetings_are_small_talk(text):
    assert wc.is_small_talk(text)


@pytest.mark.parametrize("text", ["hi, who are our top competitors?", "Hey can you size the Kenyan market?",
                                  "who are our buyers?"])
def test_real_questions_are_not_small_talk(text):
    assert not wc.is_small_talk(text)


def test_a_greeting_gets_a_short_hello_from_the_offer_specialist_not_research(llm):
    calls, _ = llm
    result = wc.reply("hey", [], CONTEXT)
    labels = [label for label, _ in calls]
    assert result.domain == "product" and "chat_route" not in labels and "chat_answer:greeting" in labels
    greeting = next(m for label, m in calls if label == "chat_answer:greeting")[0].content
    assert "Zawadi Otieno (competition)" in greeting and "RunPod" not in greeting  # the team, not the research


def test_every_answer_ends_with_three_fresh_suggestions(llm):
    result = wc.reply("Hey", [], CONTEXT)
    assert result.suggestions == ["Who should we target first?", "How do we price it?", "Extra"]  # never echoes "hey"
    answered = wc.reply("Who is our biggest threat?", [], CONTEXT)
    assert len(answered.suggestions) == wc.SUGGESTION_COUNT

