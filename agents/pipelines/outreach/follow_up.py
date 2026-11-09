"""A follow-up to someone who hasn't answered the founder's email: written
from the thread so far with the follow-up playbook. Each one adds one new
thing (never "just bumping this"), each is shorter than the last, and nothing
is claimed that isn't on file. Plain text, signed by the founder; the founder
sends it, in the same thread.

Unit-testable with a stubbed writer (`write`), like the other outreach writers.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.prompts.playbook_library import playbook_section
from agents.schemas.outreach import OutreachDraft

# The longest each follow-up may be, by its place in the sequence.
MAX_WORDS = {1: 80, 2: 50}

Write = Callable[[Sequence, str], OutreachDraft]


@dataclass(frozen=True)
class FollowUpBrief:
    sender_name: str
    contact_name: str | None
    company: str
    # What the startup sells, from its facts: the only claims allowed.
    offer: str
    # The founder's earlier emails in this thread, oldest first.
    earlier: list[str]
    # 1 for the first follow-up, 2 for the second (the last).
    step: int
    # What the founder asked for, and the team's standing instructions.
    note: str | None = None


_PROMPT = """You write a follow-up email for {sender}, who emailed {who} at
{company} and got no answer. Write as {sender}, in the first person, plain
text. It goes in the same thread, under the earlier emails, so don't repeat
them and add no subject.

This is follow-up {step} of 2.{last}
- At most {max_words} words, shorter than the email before it.
- Add ONE new thing: a fresh angle on their problem, a short useful idea, or a
  new reason to talk now. Never "just bumping this" or "following up on my
  last email" on its own.
- Greet them: "Hi {first},". Sign off with just "{sender}".
- Keep the same small ask as before, or a smaller one. No exclamation marks.
- Every fact, number, customer or result must come from WHAT WE SELL or the
  earlier emails. If you have nothing new that is true, make it a short, kind
  check-in that closes the loop rather than invent something.
{method}{note}
WHAT WE SELL
{offer}

EARLIER EMAILS (oldest first)
{earlier}"""

_LAST = ("\n- This is the last one: it may close the loop politely (\"If this isn't a priority, no problem, "
         "I'll leave it here.\").")


def _default_write(messages: Sequence, log_label: str) -> OutreachDraft:
    return invoke_structured_with_fallback(messages, OutreachDraft, log_label=log_label)


def lint(brief: FollowUpBrief, draft: OutreachDraft) -> list[str]:
    """Mechanical checks the writer can miss."""
    body = draft.body.strip()
    problems = []
    if len(body.split()) > MAX_WORDS[brief.step]:
        problems.append(f"Keep it under {MAX_WORDS[brief.step]} words")
    if "!" in body:
        problems.append("Remove exclamation marks")
    if brief.sender_name and not body.endswith(brief.sender_name):
        problems.append(f'Sign off with just "{brief.sender_name}"')
    if any(phrase in body.lower() for phrase in ("just bumping", "bumping this", "circling back")):
        problems.append("Add something new instead of bumping the thread")
    return problems


def write_follow_up(brief: FollowUpBrief, write: Write = _default_write) -> OutreachDraft:
    """The follow-up, rewritten once if it fails the checks (the second
    version is kept either way); no subject, as it is sent as a reply in the
    thread."""
    first = (brief.contact_name or "").split(" ")[0] or "there"
    prompt = _PROMPT.format(
        sender=brief.sender_name, who=brief.contact_name or "someone", company=brief.company, step=brief.step,
        last=_LAST if brief.step == 2 else "", max_words=MAX_WORDS[brief.step], first=first,
        method=playbook_section("follow-up"),
        note=f"\nThe founder's note, and the team's standing instructions:\n{brief.note}\n" if brief.note else "",
        offer=brief.offer or "(nothing on file)",
        earlier="\n\n---\n\n".join(brief.earlier) or "(none)")
    label, ask = f"follow_up:{brief.step}", HumanMessage(content="Write the follow-up now.")
    draft = write([SystemMessage(content=prompt), ask], label)
    if problems := lint(brief, draft):
        fix = "\n\nYour last version was rejected. Fix: " + "; ".join(problems)
        draft = write([SystemMessage(content=prompt + fix), ask], label)
    return draft.model_copy(update={"subject": ""})
