"""Checks for the live GTM chain. Each records a finding instead of stopping
the run, so one paid run yields the whole scorecard; the test fails at the end
if any `critical` finding was recorded.

critical -- wrong or unusable output (wrong offer, invented contact, no data)
major    -- usable but clearly below the bar (a country missing, thin profiles)
minor    -- polish (a weak subject line, a missing summary)
"""

import json
import re
from dataclasses import dataclass, field

from agents.helpers import name_in_text
from agents.pipelines.chat import workspace_chat
from agents.pipelines.outreach import grounding

from backend.tests.live.offers import GEO, Offer

_PROMISE = re.compile(r"\bI(?:'ll| will) (?:draft|prepare|send|schedule|create|put together|build)\b", re.I)
_AS_AI = re.compile(r"\bas an ai\b(?!-)|\blanguage model\b", re.I)  # not "as an AI-native bank"
_FIRST_PERSON = re.compile(r"\bI(?:'m|'d|'ve)?\b|\b(?i:my|we|we're|our|us)\b")


@dataclass
class Scorecard:
    offer: str
    checks: list[dict] = field(default_factory=list)
    # The intake conversation: each question the agent asked and the answer given.
    intake: list[dict] = field(default_factory=list)

    def check(self, stage: str, ok: bool, what: str, severity: str = "major", detail: str = "") -> bool:
        self.checks.append({"stage": stage, "ok": bool(ok), "check": what, "severity": severity,
                            "detail": "" if ok else detail})
        return bool(ok)

    def failures(self, severity: str | None = None) -> list[dict]:
        return [c for c in self.checks if not c["ok"] and (severity is None or c["severity"] == severity)]


def _text(value) -> str:
    return str(value or "").lower()


def covers(texts, countries=GEO) -> list[str]:
    """The countries none of `texts` mentions."""
    blob = " ".join(_text(t) for t in texts)
    return [c for c in countries if c.lower() not in blob]


def check_description(card: Scorecard, offer: Offer, description: str, stage: str = "intake") -> None:
    text = _text(description)
    missing = [terms for terms in offer.must_mention if not any(t in text for t in terms)]
    card.check(stage, not missing, "description states what the offer is", "critical",
               f"missing {missing}: {description[:300]}")
    mixed = [c for c in offer.conflations if c in text]
    card.check(stage, not mixed, "description doesn't borrow a sibling offer's claims", "critical", f"{mixed}")


def check_discovery(card: Scorecard, offer: Offer, insights: dict, workspace) -> None:
    card.check("discovery", workspace.offer_type == offer.offer_type, "offer type recorded", "critical",
               f"{workspace.offer_type}")
    snapshot = insights.get("offer_snapshot") or {}
    card.check("discovery", offer.name.lower() in _text(snapshot.get("offer_name")), "named offer kept",
               "critical", f"{snapshot.get('offer_name')}")
    check_description(card, offer, snapshot.get("offer_description") or "", "discovery")

    team = insights.get("specialists") or []
    domains = {s.get("domain") for s in team}
    card.check("specialists", len(team) == 4 and {"market", "competition", "gtm"} <= domains
               and bool(domains & {"product", "service"}), "four specialists, one per domain", "critical", f"{domains}")
    repeats = [s.get("role") for s in team if _text(s.get("role")).replace(" ", "")
               in {f"{d}specialist" for d in ("product", "service", "market", "competition", "gtm")}]
    card.check("specialists", not repeats, "roles are job titles, not the domain again", "minor", f"{repeats}")

    understanding = insights.get("domain_understanding") or ""
    card.check("offer", bool(understanding.strip()), "domain understanding written", "major")
    research = insights.get("research") or {}
    for stage in ("offer", "market", "competition", "icp"):
        notes = research.get(stage) or ""
        card.check(stage if stage != "offer" else "offer", len(notes) > 1500,
                   f"{stage} research notes saved with substance", "major", f"{len(notes)} chars")
    researched = _text(understanding) + _text(research.get("offer")) + _text(json.dumps(insights.get("market_data")))
    mixed = [c for c in offer.conflations if c in researched]
    card.check("offer", not mixed, "research doesn't describe a sibling offer", "critical", f"{mixed}")

    market = insights.get("market_data") or {}
    card.check("market", not covers(market.get("target_geo") or []), "market covers all three countries",
               "major", f"target_geo={market.get('target_geo')}")
    for key in ("market_demand", "willingness_to_pay", "market_fit_reasoning"):
        card.check("market", bool(market.get(key)), f"market {key} filled", "minor")

    profile = insights.get("ideal_competitor_profile") or {}
    card.check("competition", len(profile.get("archetypes") or []) >= 3, "at least 3 competitor archetypes", "major",
               f"{len(profile.get('archetypes') or [])}")
    swod = insights.get("competition_data") or {}
    card.check("competition", all(swod.get(k) for k in ("strengths", "weaknesses", "differentiators")),
               "offer-vs-category SWOD filled", "major")

    buyer = _text(market.get("buyer_type"))
    expected = {"b2c", "both"} if offer.buyer == "b2c" else {"b2b", "both"}
    card.check("market", buyer in expected, f"buyer type read as {offer.buyer.upper()}", "critical", f"got {buyer}")
    icp = insights.get("icp") or {}
    if offer.buyer == "b2c":
        card.check("icp", bool(icp.get("buyer_personas")), "ICP names consumer personas", "major")
        card.check("icp", bool(icp.get("target_channels")), "ICP names channels where they gather", "major")
    card.check("icp", not covers(icp.get("geo") or []), "ICP covers all three countries", "major", f"geo={icp.get('geo')}")
    for key in ("buyer_titles", "messaging_angles", "pain_signals"):
        card.check("icp", bool(icp.get(key)), f"ICP {key} filled", "major")
    card.check("icp", bool(icp.get("beachhead")), "ICP names a beachhead", "minor")


def check_competitors(card: Scorecard, offer: Offer, competitors: list) -> None:
    card.check("competitors", len(competitors) >= 3, "at least 3 real competitors found", "critical", f"{len(competitors)}")
    own = [c.name for c in competitors if any(d in _text(c.website) for d in offer.own_domains)]
    card.check("competitors", not own, "the offer itself is not filed as a competitor", "critical", f"{own}")
    for c in competitors:
        gaps = len(c.unsourced_fields or [])
        card.check("competitors", gaps <= 8, f"{c.name}: profile has substance", "major", f"{gaps} fields not found")
        card.check("competitors", bool(c.description or c.offering), f"{c.name}: says what they sell", "major")
    with_socials = [c for c in competitors if c.tracking_sources]
    card.check("competitors", len(with_socials) * 2 >= len(competitors), "most competitors have socials to monitor",
               "major", f"{len(with_socials)}/{len(competitors)}")


def check_monitor(card: Scorecard, competitors: list, signals: list) -> None:
    checked = [c for c in competitors if c.last_checked_at]
    card.check("monitor", len(checked) == len(competitors), "every competitor got its first check", "major",
               f"{len(checked)}/{len(competitors)}")
    titles = [s.title for s in signals]
    card.check("monitor", any(t.startswith("Now monitoring") for t in titles), "feed announces monitoring", "major",
               f"{titles}")
    changes = [s for s in signals if s.entity != "Competitor monitoring" and s.category == "competitor"
               and not s.title.startswith("New competitor")]
    card.check("monitor", all(s.source_url for s in changes), "every reported change cites a source", "major")


def _host(url) -> str:
    return re.sub(r"^https?://", "", _text(url)).split("/")[0].removeprefix("www.")


def check_accounts(card: Scorecard, offer: Offer, accounts: list, competitors: list) -> None:
    card.check("accounts", len(accounts) >= 3, "at least 3 target accounts", "critical", f"{len(accounts)}")
    off_limits = {*offer.own_domains, *(_host(c.website) for c in competitors)}
    clashing = [a.name for a in accounts if _host(a.website) in off_limits]
    card.check("accounts", not clashing, "no competitor (or the offer itself) is a target", "critical", f"{clashing}")
    countries = [g for g in GEO if any(g.lower() in _text(a.geo) for a in accounts)]
    card.check("accounts", len(countries) >= 2, "targets span at least two of the countries", "major", f"{countries}")
    for a in accounts:
        contacts = [c for c in a.key_contacts or [] if c.get("email") or c.get("linkedin")]
        card.check("accounts", bool(contacts or a.socials), f"{a.name}: someone to contact", "critical")
        if a.account_type == "company":
            card.check("accounts", bool(contacts), f"{a.name}: an email or LinkedIn contact", "major",
                       f"socials only: {a.socials}")
        card.check("accounts", len(covers([a.geo])) < len(GEO), f"{a.name}: in a target country", "major", f"geo={a.geo}")
        card.check("accounts", bool((a.trigger_event or {}).get("source")), f"{a.name}: trigger has a source", "critical")
        card.check("accounts", bool(a.summary), f"{a.name}: summary written", "minor")
    companies = [a for a in accounts if a.account_type == "company"]
    named = [a for a in companies if any(c.get("name") for c in a.key_contacts or [])]
    card.check("accounts", len(named) * 2 >= len(companies), "most companies name a person", "major",
               f"{len(named)}/{len(companies)}")


def check_b2c_reach(card: Scorecard, accounts: list, drafts: list) -> None:
    """Consumer offers reach people through venues, pitched as partners."""
    venues = [a for a in accounts if a.account_type != "company"]
    card.check("accounts", bool(venues), "B2C: some targets are venues (communities, creators, events)", "major",
               f"types={sorted({a.account_type for a in accounts})}")
    by_id = {a.id: a for a in accounts}
    for draft in drafts:
        account = by_id.get(draft.account_id)
        if account is not None and account.account_type != "company":
            body = _text(draft.body)
            card.check("outreach", any(w in body for w in ("partner", "collab", "co-host", "sponsor", "your members",
                                                          "your audience", "your community", "your followers",
                                                          "workshop", "session", "feature")),
                       f"{account.name}: pitched as a partnership", "major", draft.body[:160])


def check_outreach(card: Scorecard, offer: Offer, draft, account, problems: list[str], sources: str) -> None:
    card.check("outreach", not problems, f"{account.name}: passes the mechanical checks", "major", "; ".join(problems))
    # The writer also read the account's pages, which the harness doesn't hold,
    # so an unknown number is major (to be read), not critical.
    numbers = grounding.unsupported_numbers(f"{draft.subject or ''} {draft.body}", sources)
    card.check("outreach", not numbers, f"{account.name}: every number has a source", "major", f"{numbers}")
    proof = [p for p in grounding.problems(draft.body, sources) if "claims results or customers" in p]
    card.check("outreach", not proof, f"{account.name}: no generic proof", "critical", "; ".join(proof))
    subject = _text(draft.subject)
    card.check("outreach", draft.channel != "email" or any(t in subject for t in _text(account.name).split()[:2]),
               f"{account.name}: subject is about them", "minor", draft.subject or "")
    body = _text(draft.body)
    says_what = name_in_text(offer.name, draft.body) and any(t in body for fact in offer.must_mention for t in fact)
    card.check("outreach", says_what, f"{account.name}: says what {offer.name} does for them", "major", draft.body[:200])
    mixed = [c for c in offer.conflations if c in _text(draft.body)]
    card.check("outreach", not mixed, f"{account.name}: no sibling-offer claims", "critical", f"{mixed}")


def check_reply(card: Scorecard, kind: str, reply, draft, slots: list[str], sender: str = "", account=None) -> None:
    expected = {"question": {"question", "interested"}, "meeting": {"meeting_request", "interested"},
                "unsubscribe": {"unsubscribe"}, "ooo": {"out_of_office"}}[kind]
    card.check("replies", reply.intent in expected, f"{kind}: intent read correctly", "critical", f"got {reply.intent}")
    if kind == "ooo":
        card.check("replies", draft is None, "out-of-office gets no draft", "major")
        return
    if kind == "unsubscribe":
        card.check("replies", bool(account and account.do_not_contact), "unsubscribe marks the account do-not-contact",
                   "critical")
        if draft is not None:
            card.check("replies", len(draft.body.split()) <= 70, "unsubscribe reply is short, no pitch", "major")
        return
    card.check("replies", draft is not None, f"{kind}: a reply is drafted", "critical")
    if draft is None:
        return
    body = _text(draft.body)
    first = sender.split(" ")[0].lower()
    card.check("replies", not (first and re.match(rf"^(hi|hello|dear)\s+{first}\b", body)),
               f"{kind}: greets the contact, not the sender", "major", draft.body[:60])
    if kind == "meeting":
        offered = [s for s in slots if s.split(",")[0].lower() in body or s.split(" ")[0].lower() in body]
        card.check("replies", bool(offered), "meeting reply offers the real free slots", "major", draft.body[:300])


def check_chat(card: Scorecard, question: str, expected: set[str], message) -> None:
    card.check("chat", message.specialist_domain in expected, f"'{question[:50]}' goes to the right specialist",
               "major", f"got {message.specialist_domain}, expected {expected}")
    content = message.content or ""
    card.check("chat", bool(_FIRST_PERSON.search(content)), "answers in the first person", "major")
    card.check("chat", not _PROMISE.search(content), "no promises of later actions", "major",
               (_PROMISE.search(content) or [""])[0])
    card.check("chat", not _AS_AI.search(content), "never calls itself an AI", "major")
    claimed = workspace_chat.voice_problems(content)
    card.check("chat", not any("haven't done that" in p for p in claimed), "claims no work it didn't do", "major",
               "; ".join(claimed))
    card.check("chat", len(content) > 400, "answer has depth", "minor", f"{len(content)} chars")
