"""A reply doesn't repeat, in text, the options its blocks already offer."""

from agents.lace.reply_tidy import without_repeated_options

FINDING = ("The search found 4 procurement roles, but none are AI/Web3 opportunities. They're traditional "
           "business needs that don't match what we build.")

NUMBERED = FINDING + """

Would you like me to:

1. **Dismiss all 4** and try a different approach?

2. **Keep only Deloitte** (moderate fit)?

3. **Search specifically** for "Blockchain Developer" posts?

Which approach works best for finding true AI/Web3 opportunities?"""

UNMARKED = FINDING + """

Would you like me to:

Dismiss all 4 and try a different approach?
Keep only Deloitte East Africa and Kericho Gold Tea?
Search specifically for job postings mentioning "AI Engineer"?
Which approach works best for finding true AI/Web3 opportunities?"""


def test_a_choice_block_takes_the_options_and_the_question_off_the_text():
    assert without_repeated_options(NUMBERED, {"choices"}) == FINDING
    assert without_repeated_options(UNMARKED, {"choices"}) == FINDING


def test_suggested_replies_take_the_list_but_leave_the_question():
    reply = FINDING + "\n\nI could:\n- Dig into Velinex\n- Find target accounts\n\nWant me to start?"
    assert without_repeated_options(reply, {"suggestions"}) == reply
    listed = FINDING + "\n\nNext, I could:\n- Dig into Velinex\n- Find target accounts"
    assert without_repeated_options(listed, {"suggestions"}) == FINDING


def test_nothing_changes_without_a_block_that_offers_options():
    assert without_repeated_options(NUMBERED, set()) == NUMBERED
    assert without_repeated_options(NUMBERED, {"card", "action"}) == NUMBERED


def test_a_question_that_also_says_something_stays():
    reply = "I found three rivals. Want me to track them?"
    assert without_repeated_options(reply, {"choices"}) == reply
    assert without_repeated_options(FINDING + "\n\nShall we go?", {"choices"}) == FINDING


def test_one_list_item_is_content_not_options():
    reply = FINDING + "\n\n- One thing worth noting: they hire in Q1."
    assert without_repeated_options(reply, {"choices"}) == reply


def test_a_reply_that_is_only_options_is_left_whole():
    only = "1. Dismiss them?\n2. Keep them?"
    assert without_repeated_options(only, {"choices"}) == only
