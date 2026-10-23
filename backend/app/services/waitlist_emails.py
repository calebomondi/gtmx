"""The waitlist's two emails: "you're on the list", and "you're in line for
the pilot" when someone opts in. Plain words, the brand mark, one link."""

from datetime import UTC, date, datetime
from html import escape

from backend.app.services import email
from config import settings


def _html(paragraphs: list[str]) -> str:
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{escape(p)}</p>' for p in paragraphs)
    return email.branded_html(body, "Reply to this email to be removed from the list.")


def _day(day: date) -> str:
    return f"{day:%B} {day.day}"


def _pilot_when(today: date) -> str:
    """When the current cohort starts, said as of `today`."""
    starts = settings.waitlist_pilot_starts_on
    if starts > today:
        return f"Our pilot for {settings.waitlist_pilot_spots} founders starts {_day(starts)}."
    return f"Our pilot for {settings.waitlist_pilot_spots} founders has been running since {_day(starts)}."


def joined(today: date | None = None) -> tuple[str, str, str]:
    """(subject, text, html) for a new signup."""
    today = today or datetime.now(UTC).date()
    paragraphs = [
        "You're on the Thalace waitlist.",
        "Thalace gives your startup its own assistant, Lace. Give it your website and it learns what you sell, "
        "then finds your ideal customers and the people to reach, spots places to sell, showcase and partner, "
        "watches your competitors, brainstorms with you, and drafts every message and reply. Nothing is ever "
        "sent without your click.",
        f"{_pilot_when(today)} If you'd like a spot and didn't ask for one when you signed up, just reply \"pilot\".",
        "Thanks for joining early.",
        "The Thalace team",
    ]
    return "You're on the Thalace waitlist", "\n\n".join(paragraphs), _html(paragraphs)


def pilot(today: date | None = None) -> tuple[str, str, str]:
    """(subject, text, html) for someone who asked to join the pilot."""
    today = today or datetime.now(UTC).date()
    paragraphs = [
        "You're in line for the Thalace pilot.",
        f"{_pilot_when(today)} Within {settings.waitlist_pilot_contact_days} days we'll email you to set up your "
        "Lace and a short kickoff call.",
        "Pilots get their own Lace free, talk to the team directly, and shape what Lace learns next. All we ask "
        "is a 20-minute feedback call every two weeks.",
        "The Thalace team",
    ]
    return "You're in line for the Thalace pilot", "\n\n".join(paragraphs), _html(paragraphs)
