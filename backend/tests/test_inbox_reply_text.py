"""A synced email reply keeps the reply's own words, not the mail it quotes."""

import importlib.util
from pathlib import Path

import pytest

from backend.app.services.inbox import reply_only

_MIGRATION = Path(__file__).parents[1] / "app/database/migrations/versions/20261022_1200_strip_quotes_from_email_replies.py"
_spec = importlib.util.spec_from_file_location("strip_quotes_migration", _MIGRATION)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)

GMAIL = """Hey Caleb,

Where can we book a call?

Kaleb Mokua,
Thalace Labs

On Thu, Oct 22, 2026, 15:14 Caleb Mokua <caleb@shanga.test> wrote:

> Hi Kaleb,
>
> Scaling sensors from 300 to 2,000 farms
"""


@pytest.mark.parametrize("text, reply", [
    (GMAIL, "Hey Caleb,\n\nWhere can we book a call?\n\nKaleb Mokua,\nThalace Labs"),
    ("Sure.\n\nOn Thu, Oct 22, 2026 at 3:14 PM Caleb Mokua <\ncaleb@shanga.test> wrote:\n> hi", "Sure."),
    ("Yes, Tuesday.\n\n-----Original Message-----\nFrom: Caleb\nSent: Monday", "Yes, Tuesday."),
    ("Thanks\n\nFrom: Caleb Mokua\nSent: Monday, 20 October\nTo: Kaleb", "Thanks"),
    ("Agreed.\n> earlier line", "Agreed."),
    ("I wrote: the plan is on page 2.\nOn Monday we start.", "I wrote: the plan is on page 2.\nOn Monday we start."),
    ("> nothing but a quote", "> nothing but a quote"),
])
def test_reply_only(text, reply):
    assert reply_only(text) == reply
    # The backfill's frozen copy cleans stored replies the same way.
    assert migration._reply_only(text) == reply
