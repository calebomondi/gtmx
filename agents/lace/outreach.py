"""First-touch outreach for a Lace's target accounts: v1's GTM specialist
pipeline, briefed from the Lace.

v1's pipeline (pipelines/outreach/gtm_specialist) researches the account's
own pages, plans an angle, consults the product, market and competition
specialists, writes, reviews against a rubric and runs the grounding checks
that strip any number or claim no source backs. A Lace has no specialist team,
so the "research" each specialist answers from is the Lace's own facts on that
domain; the personas fall back to v1's generic ones.

A draft is only ever a draft: sending is the founder's decision.
"""

from collections.abc import Callable
from dataclasses import dataclass

from agents.lace.accounts import record_brief
from agents.lace.prompts import render_brief
from agents.pipelines.outreach import gtm_specialist
from agents.schemas.accounts import AccountRecord
from agents.schemas.lace import CompetitorSummary, Fact, LaceProfile
from agents.schemas.outreach import OutreachDraft

RESEARCH_TOKENS = 700
# The organisation's own accounts a message can go to, best first. Not its
# LinkedIn page: a company page cannot be messaged.
ORG_DM_CHANNELS = ("x", "instagram", "facebook", "tiktok")
COMPETITORS_SHOWN = 8
# The facts each consulted specialist answers from.
_DOMAIN_TOPICS = {
    "product": ("offer", "pricing", "customers", "positioning"),
    "market": ("market", "icp", "customers"),
    "competition": ("competition", "positioning"),
}

# v1's writer, injectable so tests can script it: (brief, offer name) -> draft.
Write = Callable[[gtm_specialist.OutreachBrief, str], OutreachDraft]


@dataclass(frozen=True)
class Recipient:
    channel: str  # email | linkedin | x | instagram | facebook | tiktok
    name: str | None
    title: str | None
    address: str  # an email address, or the profile or page URL


def recipient_for(record: AccountRecord) -> Recipient | None:
    """Who the first message goes to: a named person with an email, else a
    named person on LinkedIn, else the organisation's own email, else its own
    account on X, Instagram, Facebook or TikTok. None when there is nothing to
    reach them on."""
    people = [c for c in record.key_contacts if c.name]
    for c in people:
        if c.email:
            return Recipient("email", c.name, c.title, c.email)
    for c in people:
        if c.linkedin:
            return Recipient("linkedin", c.name, c.title, c.linkedin)
    for c in record.key_contacts:
        if c.email:
            return Recipient("email", None, None, c.email)
    for platform in ORG_DM_CHANNELS:
        if record.socials.get(platform):
            return Recipient(platform, None, None, record.socials[platform])
    return None


def research_by_domain(facts: list[Fact], competitors: list[CompetitorSummary]) -> dict[str, str]:
    research = {domain: render_brief([f for f in facts if f.topic in topics], cap=RESEARCH_TOKENS)
                for domain, topics in _DOMAIN_TOPICS.items()}
    rivals = "\n".join(f"- {c.name}: {c.summary or ''}" for c in competitors[:COMPETITORS_SHOWN])
    if rivals:
        research["competition"] += f"\nTracked competitors:\n{rivals}"
    return research


def draft_first_touch(profile: LaceProfile, facts: list[Fact], competitors: list[CompetitorSummary],
                      record: AccountRecord, recipient: Recipient, sender_name: str,
                      write: Write = gtm_specialist.write_first_touch) -> OutreachDraft:
    seller = profile.startup_name or profile.website
    offer_facts = [f for f in facts if f.topic in _DOMAIN_TOPICS["product"]]
    brief = gtm_specialist.OutreachBrief(
        channel=recipient.channel, sender_name=sender_name, offer=render_brief(offer_facts),
        account=record_brief(record), contact_name=recipient.name, contact_title=recipient.title,
        website=record.website, trigger_source=record.trigger_event.source if record.trigger_event else None,
        seller=seller, account_type=record.account_type, research=research_by_domain(facts, competitors),
    )
    return write(brief, seller)
