"""The follow-up writer: written from the thread with the follow-up playbook,
shorter at each step, rewritten once when it fails the checks, and sent with
no subject (a reply in the thread)."""

from agents.pipelines.outreach.follow_up import MAX_WORDS, FollowUpBrief, lint, write_follow_up
from agents.schemas.outreach import OutreachDraft

BRIEF = FollowUpBrief(sender_name="Wanjiku", contact_name="Ada Lovelace", company="Acme Clinics",
                      offer="Payline: payroll for clinic groups, KES 200 per staff a month.",
                      earlier=["Hi Ada, ... cutting payroll time across your 12 sites ... Wanjiku"], step=1)
GOOD = "Hi Ada,\n\nOne idea for the new Westlands site: run its first payroll on Payline as a trial.\n\nWanjiku"


def _writer(*bodies):
    seen = []

    def write(messages, label):
        seen.append((label, messages[0].content))
        return OutreachDraft(subject="Should be dropped", body=bodies[min(len(seen), len(bodies)) - 1])
    return write, seen


def test_it_writes_from_the_thread_with_the_playbook():
    write, seen = _writer(GOOD)
    draft = write_follow_up(BRIEF, write)
    assert (draft.subject, draft.body) == ("", GOOD)
    [(label, prompt)] = seen
    assert label == "follow_up:1" and "At most 80 words" in prompt and "THE FOLLOW-UP PLAYBOOK" in prompt
    assert "cutting payroll time across your 12 sites" in prompt and "KES 200 per staff" in prompt
    assert "This is the last one" not in prompt


def test_the_second_follow_up_is_shorter_and_may_close_the_loop():
    write, seen = _writer("Hi Ada,\n\nIf this isn't a priority, no problem. I'll leave it here.\n\nWanjiku")
    write_follow_up(FollowUpBrief(**{**BRIEF.__dict__, "step": 2}), write)
    assert f"At most {MAX_WORDS[2]} words" in seen[0][1] and "This is the last one" in seen[0][1]


def test_a_failed_check_gets_one_rewrite_with_the_reasons():
    bump = "Hi Ada,\n\nJust bumping this up your inbox!\n\nWanjiku"
    write, seen = _writer(bump, GOOD)
    assert write_follow_up(BRIEF, write).body == GOOD
    assert len(seen) == 2 and "Remove exclamation marks" in seen[1][1] and "instead of bumping" in seen[1][1]


def test_lint_checks_length_and_sign_off():
    long = "Hi Ada,\n\n" + "word " * 90 + "\n\nWanjiku"
    assert lint(BRIEF, OutreachDraft(body=long)) == ["Keep it under 80 words"]
    assert lint(BRIEF, OutreachDraft(body="Hi Ada, a thought.")) == ['Sign off with just "Wanjiku"']
