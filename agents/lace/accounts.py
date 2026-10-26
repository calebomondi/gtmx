"""Finding customers for a Lace: v1's account discovery, run on the Lace's ICP,
then v1's fit case for each account found.

Discovery (trigger-first queries, a recency gate, verification that the
trigger is about the account) runs once per target country. Each kept account
then gets the seller's case: what it needs now, the capability that answers
it, the payoff and an opening angle. Synchronous and long: the backend runs it
as a background job.
"""

from collections.abc import Callable

from agents.concurrency import ContextThreadPoolExecutor
from agents.lace.prompts import render_brief
from agents.pipelines.accounts import fit as account_fit
from agents.pipelines.accounts.account_discovery import run_account_discovery_by_country
from agents.schemas.accounts import AccountFit, AccountRecord
from agents.schemas.icp import ICP
from agents.schemas.lace import Fact, LaceProfile
from utils.log import logger

FIT_WORKERS = 4
OFFER_TOKENS = 800

# The two steps, injectable so tests can script them.
Discover = Callable[[dict], dict]
Assess = Callable[[str, str, str], AccountFit]


def _lines(label: str, items: list[str]) -> str:
    return f"{label}:\n" + "\n".join(f"- {i}" for i in items) if items else ""


def record_brief(record: AccountRecord) -> str:
    """Everything discovery found about an account, as text for the fit case."""
    trigger = record.trigger_event
    parts = [
        f"Account: {record.name} ({record.account_type}; {record.website or 'no website'})",
        f"What they do: {record.summary}" if record.summary else "",
        f"Industry: {record.industry or 'n/a'}; size: {record.size or 'n/a'}; geo: {record.geo or 'n/a'}",
        f"Trigger event: {trigger.event} (source: {trigger.source})" if trigger else "",
        _lines("Why it fits the ICP", record.why_selected),
        _lines("Pain signals", record.pain_signals),
        _lines("Hiring signals", record.hiring_signals),
        _lines("Recent news", record.recent_news[:4]),
    ]
    return "\n".join(p for p in parts if p)


def _default_assess(offer: str, account: str, seller: str) -> AccountFit:
    return account_fit.assess(offer, account, seller)


def find_accounts(profile: LaceProfile, facts: list[Fact], icp: ICP, exclude_domains: list[str],
                  country: str | None = None, discover: Discover = run_account_discovery_by_country,
                  assess: Assess = _default_assess) -> list[tuple[AccountRecord, AccountFit | None]]:
    """Target accounts with a current trigger, each with the case for it (None
    where the case could not be made). `country` narrows the search to one
    place; otherwise the ICP's geographies are searched one by one."""
    if country:
        icp = icp.model_copy(update={"geo": [country]})
    state = {
        "offer_name": profile.startup_name or profile.website,
        "icp_data": icp,
        "target_market": list(icp.geo),
        "exclude_domains": exclude_domains,
        "messages": [],
    }
    accounts = list(getattr(discover(state).get("accounts"), "accounts", None) or [])
    if country:
        # The search was scoped to it; discovery does not always say so per record.
        accounts = [a if a.geo else a.model_copy(update={"geo": country}) for a in accounts]

    offer_facts = [f for f in facts if f.topic in ("offer", "pricing", "positioning", "customers")]
    offer = render_brief(offer_facts, cap=OFFER_TOKENS)
    seller = profile.startup_name or profile.website

    def case(record: AccountRecord) -> AccountFit | None:
        try:
            return assess(offer, record_brief(record), seller)
        except Exception:  # noqa: BLE001 -- one account's case failing leaves it without one
            logger.exception("Fit case for %s failed", record.name)
            return None

    with ContextThreadPoolExecutor(max_workers=FIT_WORKERS) as pool:
        fits = list(pool.map(case, accounts))
    return list(zip(accounts, fits))
