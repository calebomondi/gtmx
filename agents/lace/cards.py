"""Cards for what a Lace shows the founder in a reply, built from what it
has saved: the card says only what the saved item says."""

from collections.abc import Sequence

from agents.lace.store import LaceStore
from agents.schemas.lace import AccountSummary, CompetitorSummary, DraftSummary
from agents.schemas.lace_ui import CardBlock, CardKind
from agents.schemas.opportunities import OpportunitySummary

# Items a card can be drawn from, per lookup.
LOOKUP_LIMIT = 200
BODY_CHARS = 280


def _clip(text: str | None) -> str | None:
    text = (text or "").strip()
    return text if len(text) <= BODY_CHARS else text[:BODY_CHARS].rstrip() + "…"


def _joined(*parts: str | None, sep: str = " · ") -> str | None:
    return sep.join(p for p in parts if p) or None


def competitor_card(c: CompetitorSummary) -> CardBlock:
    return CardBlock(kind="competitor", id=c.id, title=c.name, subtitle=c.website, body=_clip(c.summary), url=c.website)


def account_card(a: AccountSummary) -> CardBlock:
    body = _joined(a.trigger, a.need and f"Need: {a.need}", sep=". ")
    return CardBlock(kind="account", id=a.id, title=a.name, subtitle=_joined(a.geo, a.fit_strength and f"{a.fit_strength} fit"),
                     body=_clip(body), url=a.website)


def opportunity_card(o: OpportunitySummary) -> CardBlock:
    when = o.deadline and f"closes {o.deadline}" or o.date and f"on {o.date}"
    return CardBlock(kind="opportunity", id=o.id, title=o.title, subtitle=_joined(o.kind, o.organiser, when),
                     body=_clip(o.why_it_fits), url=o.url)


def draft_card(d: DraftSummary) -> CardBlock:
    return CardBlock(kind="draft", id=d.id, title=f"To {d.recipient} at {d.company}", subtitle=_joined(d.channel, d.subject),
                     body=_clip(d.body))


async def cards(store: LaceStore, kind: CardKind, ids: Sequence[str]) -> tuple[list[CardBlock], list[str]]:
    """Cards for the saved or suggested items with these ids, in the order
    asked, and the ids that matched nothing of that kind."""
    if kind == "draft":
        found = {d.id: draft_card(d) for d in await store.drafts(LOOKUP_LIMIT)}
        return [found[i] for i in ids if i in found], [i for i in ids if i not in found]
    suggested = await store.suggestions(LOOKUP_LIMIT)
    if kind == "competitor":
        found = {c.id: competitor_card(c) for c in [*await store.competitors(LOOKUP_LIMIT), *suggested.competitors]}
    elif kind == "account":
        found = {a.id: account_card(a) for a in [*await store.accounts(LOOKUP_LIMIT), *suggested.accounts]}
    else:
        found = {o.id: opportunity_card(o) for o in [*await store.opportunities(LOOKUP_LIMIT), *suggested.opportunities]}
    return [found[i] for i in ids if i in found], [i for i in ids if i not in found]
