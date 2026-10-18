"""The waitlist's two emails: "you're on the list", and "you're in line for
the pilot" when someone opts in. Plain words, the brand mark, one link."""

from html import escape

from backend.app.services import email
from config import settings


def _html(paragraphs: list[str]) -> str:
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{escape(p)}</p>' for p in paragraphs)
    return email.branded_html(body, "Reply to this email to be removed from the list.")


def joined() -> tuple[str, str, str]:
    """(subject, text, html) for a new signup."""
    paragraphs = [
        "You're on the Thalace waitlist.",
        "Thalace is a go-to-market team for founders selling in Kenya, Nigeria and South Africa: it studies your "
        "offer, maps your market and rivals, finds the companies and communities with a reason to buy now, and "
        "drafts the outreach. Nothing is ever sent without your click.",
        f"We're opening a pilot for {settings.waitlist_pilot_spots} founders. If you'd like a spot and didn't "
        f"ask for one when you signed up, just reply \"pilot\".",
        "Thanks for joining early.",
        "The Thalace team",
    ]
    return "You're on the Thalace waitlist", "\n\n".join(paragraphs), _html(paragraphs)


def pilot() -> tuple[str, str, str]:
    """(subject, text, html) for someone who asked to join the pilot."""
    paragraphs = [
        "You're in line for the Thalace pilot.",
        f"There are {settings.waitlist_pilot_spots} pilot spots. Within {settings.waitlist_pilot_contact_days} "
        "days we'll email you to set up your account and a short kickoff call.",
        "Pilots use Thalace free, talk to the team directly, and decide what we build next. All we ask is a "
        "20-minute feedback call every two weeks.",
        "The Thalace team",
    ]
    return "You're in line for the Thalace pilot", "\n\n".join(paragraphs), _html(paragraphs)
