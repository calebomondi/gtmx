"""Re-check one tracked competitor and report GTM-relevant changes since the
previous check.

Change detection compares SOURCES, not LLM summaries: two summaries of an
unchanged page differ run to run, which reads as phantom changes. So the
state stores a hash and text of the site plus the news URLs already seen.
When neither changed, there are no changes and no LLM call. Only a real
change in the source goes to the LLM, which compares previous vs current raw
text (and only the new news) and judges what is material.

Pure: the backend stores the returned state and passes it back next time.
The first check only records a baseline, so tracking never floods the feed.
"""

import hashlib
import re
from datetime import date, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.pipelines.web_utils import call_with_timeout
from agents.schemas.monitor import ChangeReport, CompetitorChange
from config import get_settings
from data_sources.scraping.exa import scrape_url, search_and_scrape

_SITE_CHARS = 12_000
_NEWS_CHARS = 800
_NEWS_DAYS = 30
_TIMEOUT_S = 30

_DIFF_PROMPT = """You monitor a competitor for {our_offer}. Below are {name}'s website text at
the previous and current check, and news published since. Report only changes
that matter for go-to-market: price or plan changes, new products or
features, a positioning shift, funding, leadership changes, notable
partnerships or launches.

Ignore wording tweaks, reordering, dates, counters and anything present in
both versions. If nothing material changed, return an empty list. Every
change must be supported by the CURRENT text or a NEW news item; cite the
news URL when it is the source. importance: high = we should react this week.

PREVIOUS WEBSITE TEXT
{previous}

CURRENT WEBSITE TEXT
{current}

NEW NEWS
{news}"""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _news(name: str) -> list[dict]:
    since = (date.today() - timedelta(days=_NEWS_DAYS)).isoformat()
    return call_with_timeout(
        lambda: search_and_scrape(f'"{name}"', get_settings(), num_results=4, start_published_date=since),
        _TIMEOUT_S, default=[], label=f"monitor_news[{name}]",
    ) or []


def check(name: str, website: str, previous: dict | None, our_offer: str) -> tuple[dict, list[CompetitorChange]]:
    """Returns (new state, material changes)."""
    raw = call_with_timeout(lambda: scrape_url(website, get_settings()), _TIMEOUT_S, default="",
                            label=f"monitor_site[{website}]") or ""
    site = _normalize(raw)[:_SITE_CHARS]
    news = _news(name)
    previous = previous or {}
    seen = set(previous.get("news_urls") or [])
    fresh_news = [n for n in news if n["url"] not in seen]

    state = {
        # An unreachable site keeps the last good text, so a blip isn't a "change".
        "site_hash": hashlib.sha256(site.encode()).hexdigest() if site else previous.get("site_hash"),
        "site_text": site or previous.get("site_text", ""),
        "news_urls": sorted(seen | {n["url"] for n in news}),
    }
    if not previous:
        return state, []  # baseline
    site_changed = bool(site) and state["site_hash"] != previous.get("site_hash")
    if not site_changed and not fresh_news:
        return state, []

    report = invoke_structured_with_fallback(
        messages=[SystemMessage(content=_DIFF_PROMPT.format(
            our_offer=our_offer or "our offer", name=name,
            previous=previous.get("site_text") or "(none)",
            current=state["site_text"] if site_changed else "(unchanged)",
            news="\n\n".join(f"[{n['url']}] {n['title']}\n{(n.get('text') or '')[:_NEWS_CHARS]}" for n in fresh_news) or "(none)",
        )), HumanMessage(content="List the material changes now.")],
        schema=ChangeReport, log_label="monitor_diff", thinking=False,
    )
    return state, report.changes
