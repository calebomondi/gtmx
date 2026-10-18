"""The brief: the Lace telling its founder, unprompted, what changed and
what to do next. The digest of what happened is assembled from the database;
the Lace writes the brief from it in its own voice, as a conversation turn."""

_REQUEST = """Write the founder's {period} brief from the digest below. It is the
first thing they read{when}, so keep it under 200 words:
- What changed: the few things that matter, most important first.
- Waiting on you: drafts to review, replies to answer, deadlines coming up.
- Next: up to three concrete steps you suggest, each one line.
Leave out empty parts. Mention sources where the digest has them. Do not call
tools unless one fact needs checking.

Digest (from your own records, {since_label}):
{digest}"""


def brief_request(digest: str, frequency: str, since_label: str) -> str:
    """What the Lace is asked, in a turn of its own, to write the brief."""
    period = "weekly" if frequency == "weekly" else "daily"
    when = " this week" if frequency == "weekly" else " today"
    return _REQUEST.format(period=period, when=when, digest=digest, since_label=since_label)
