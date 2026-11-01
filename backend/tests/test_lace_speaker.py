"""The Lace is told who it is talking with, by first name, in every chat."""

from backend.app.runs.lace import speaker_note


def test_the_speaker_is_named():
    assert speaker_note("Kalev Mokua") == "You're talking with Kalev Mokua. Call them Kalev."
    assert speaker_note("  Wanjiru   Kamau ") == "You're talking with Wanjiru Kamau. Call them Wanjiru."


def test_no_name_means_no_note():
    assert speaker_note(None) is None and speaker_note("   ") is None
