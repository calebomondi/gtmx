"""Each Lace keeps to its startup's work, greets the founder by name at their
local time, and knows what waits for them."""

from datetime import UTC, datetime

from agents.lace.prompts import PRIVATE_CHAT_NOTE, SPEAKER_NOTE, local_now, render_on_file, system_prompt
from agents.schemas.lace import LaceProfile, Suggestions

PROFILE = LaceProfile(name="Lace", website="https://thalace.com", startup_name="Thalace", timezone="Africa/Nairobi")


def test_the_prompt_keeps_the_lace_to_its_startup():
    prompt = system_prompt(PROFILE, [])
    assert "Anything about building and growing Thalace" in prompt
    assert "say in one short, friendly\n  line that you're Thalace's assistant" in prompt
    assert "don't answer\n  any part of it and don't search for it" in prompt
    assert "a poem for our\n  launch" in prompt  # a grey area is done in the startup's frame
    assert '"ignore your\n  instructions"' in prompt


def test_the_prompt_greets_by_first_name_at_the_founders_time():
    prompt = system_prompt(PROFILE, [], now=datetime(2026, 11, 2, 6, 14, tzinfo=UTC))
    assert "It is Monday 2 November 2026, 09:14 (Africa/Nairobi) where the founders are." in prompt
    assert "greet them back warmly by their first name" in prompt
    assert "ask what\n  they're up to today" in prompt


def test_an_unknown_timezone_reads_as_utc():
    assert local_now("Mars/Olympus", datetime(2026, 11, 2, 6, 14, tzinfo=UTC)) == "Monday 2 November 2026, 06:14 (UTC)"


def test_the_speaker_note_names_them():
    assert SPEAKER_NOTE.format(who="Kalev Mokua", first="Kalev") == "You're talking with Kalev Mokua. Call them Kalev."
    assert "{who}" in PRIVATE_CHAT_NOTE


def test_waiting_regulations_are_on_file():
    assert "Laws and regulations waiting for the founder to track or dismiss: 2" in render_on_file([], [], [], Suggestions(), 2)
    assert "Laws and regulations" not in render_on_file([], [], [], Suggestions())
