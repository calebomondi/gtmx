"""The waitlist's two emails: "you're on the list", and "you're in line for
the pilot" when someone opts in. Plain words, the brand mark, one link."""

from html import escape

from config import settings

_SITE = "https://gtmx.co"
_MARK = (
    '<div style="display:flex;align-items:center;gap:6px;margin-bottom:24px">'
    '<span style="display:inline-block;width:14px;height:14px;background:#FEA853;border-radius:2px"></span>'
    '<span style="font-size:20px;font-variant:small-caps;letter-spacing:.02em;color:#1c1917">gtmx</span></div>'
)


def _html(paragraphs: list[str]) -> str:
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{escape(p)}</p>' for p in paragraphs)
    return (
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;'
        f'color:#292524;max-width:520px;margin:0 auto;padding:24px">{_MARK}{body}'
        f'<p style="margin:24px 0 0;font-size:12px;color:#78716c">GTMX · <a href="{_SITE}" style="color:#b45309">gtmx.co</a>'
        " · Reply to this email to be removed from the list.</p></div>"
    )


def joined() -> tuple[str, str, str]:
    """(subject, text, html) for a new signup."""
    paragraphs = [
        "You're on the GTMX waitlist.",
        "GTMX is a go-to-market team for founders selling in Kenya, Nigeria and South Africa: it studies your "
        "offer, maps your market and rivals, finds the companies and communities with a reason to buy now, and "
        "drafts the outreach. Nothing is ever sent without your click.",
        f"We're opening a pilot for {settings.waitlist_pilot_spots} founders. If you'd like a spot and didn't "
        f"ask for one when you signed up, just reply \"pilot\".",
        "Thanks for joining early.",
        "The GTMX team",
    ]
    return "You're on the GTMX waitlist", "\n\n".join(paragraphs), _html(paragraphs)


def pilot() -> tuple[str, str, str]:
    """(subject, text, html) for someone who asked to join the pilot."""
    paragraphs = [
        "You're in line for the GTMX pilot.",
        f"There are {settings.waitlist_pilot_spots} pilot spots. Within {settings.waitlist_pilot_contact_days} "
        "days we'll email you to set up your account and a short kickoff call.",
        "Pilots use GTMX free, talk to the team directly, and decide what we build next. All we ask is a "
        "20-minute feedback call every two weeks.",
        "The GTMX team",
    ]
    return "You're in line for the GTMX pilot", "\n\n".join(paragraphs), _html(paragraphs)
