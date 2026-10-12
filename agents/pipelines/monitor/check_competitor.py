"""Re-check one tracked competitor and report GTM-relevant changes since the
previous check: its website, news, events it runs or attends, and its social
posts.

Change detection compares SOURCES, not LLM summaries: two summaries of an
unchanged page differ run to run, which reads as phantom changes. So the
state stores a hash and text of the site plus the news/event/post URLs
already seen. When none of them changed, there are no changes and no LLM
call. Only a real change in the source goes to the LLM, which compares
previous vs current raw text (and only the new items) and judges what is
material.

The first check records the baseline and reports only what is notable from
the last month (recent news, upcoming events, recent posts), so a user sees
what their rivals are doing the moment tracking starts, without a flood.

Pure: the backend stores the returned state and passes it back next time.
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
_ITEM_CHARS = 800
_NEWS_DAYS = 30
_NEWS_RESULTS = 4
_EVENT_RESULTS = 3
_FIRST_CHECK_MAX = 3
_TIMEOUT_S = 30

_SOURCES = """NEW NEWS
{news}

NEW EVENTS (webinars, conferences, launches they run or appear at)
{events}

NEW SOCIAL POSTS
{posts}"""

_DIFF_PROMPT = """You monitor a competitor for {our_offer}. Below are {name}'s website text at
the previous and current check, plus news, events and social posts that are
new since then. Report only changes that matter for go-to-market: price or
plan changes, new products or features, a positioning shift, funding,
leadership changes, notable partnerships, launches, events they are running
or speaking at, and social posts that announce any of these or show a
campaign push.

Ignore wording tweaks, reordering, dates, counters, routine engagement posts
and anything present in both versions. If nothing material changed, return
an empty list. Every change must be supported by the CURRENT text or a NEW
item; cite its URL. importance: high = we should react this week.

PREVIOUS WEBSITE TEXT
{previous}

CURRENT WEBSITE TEXT
{current}

""" + _SOURCES

_FIRST_PROMPT = """You have just started monitoring {name}, a competitor of {our_offer}. Below
is what was published about them in the last month. Report at most
{limit} items a go-to-market team should know about now: launches, pricing,
funding, partnerships, events they run or speak at, campaigns. Skip routine
posts and anything older or immaterial; an empty list is fine. Cite each
item's URL. importance: high = we should react this week.

""" + _SOURCES


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _search(query: str, results: int, label: str) -> list[dict]:
    since = (date.today() - timedelta(days=_NEWS_DAYS)).isoformat()
    return call_with_timeout(
        lambda: search_and_scrape(query, get_settings(), num_results=results, start_published_date=since),
        _TIMEOUT_S, default=[], label=label,
    ) or []


def _news(name: str) -> list[dict]:
    return _search(f'"{name}"', _NEWS_RESULTS, f"monitor_news[{name}]")


def _events(name: str) -> list[dict]:
    return _search(f'"{name}" webinar conference summit event launch', _EVENT_RESULTS, f"monitor_events[{name}]")


def _items(docs: list[dict]) -> str:
    return "\n\n".join(f"[{d['url']}] {d.get('title') or ''}\n{(d.get('text') or '')[:_ITEM_CHARS]}" for d in docs) or "(none)"


def _posts(posts: list[dict]) -> str:
    return "\n\n".join(
        f"[{p.get('url') or p.get('platform')}] {p.get('platform', '')} {p.get('date') or ''}\n{(p.get('text') or '')[:_ITEM_CHARS]}"
        for p in posts
    ) or "(none)"


def _report(prompt: str, label: str) -> list[CompetitorChange]:
    report = invoke_structured_with_fallback(
        messages=[SystemMessage(content=prompt), HumanMessage(content="List the material changes now.")],
        schema=ChangeReport, log_label=label, thinking=False,
    )
    return report.changes


def check(name: str, website: str, previous: dict | None, our_offer: str,
          posts: list[dict] | None = None) -> tuple[dict, list[CompetitorChange]]:
    """Returns (new state, material changes). `posts` are the competitor's
    recent social posts ({platform, text, url, date}), when socials were
    refreshed this run."""
    raw = call_with_timeout(lambda: scrape_url(website, get_settings()), _TIMEOUT_S, default="",
                            label=f"monitor_site[{website}]") or ""
    site = _normalize(raw)[:_SITE_CHARS]
    news, events = _news(name), _events(name)
    previous = previous or {}
    seen = set(previous.get("news_urls") or [])
    seen_posts = set(previous.get("post_urls") or [])
    fresh_news = [n for n in news if n["url"] not in seen]
    fresh_events = [e for e in events if e["url"] not in seen and e["url"] not in {n["url"] for n in fresh_news}]
    fresh_posts = [p for p in posts or [] if p.get("url") and p["url"] not in seen_posts]

    state = {
        # An unreachable site keeps the last good text, so a blip isn't a "change".
        "site_hash": hashlib.sha256(site.encode()).hexdigest() if site else previous.get("site_hash"),
        "site_text": site or previous.get("site_text", ""),
        "news_urls": sorted(seen | {d["url"] for d in news + events}),
        "post_urls": sorted(seen_posts | {p["url"] for p in posts or [] if p.get("url")}),
    }
    sources = {"news": _items(fresh_news), "events": _items(fresh_events), "posts": _posts(fresh_posts)}

    if not previous:
        if not (fresh_news or fresh_events or fresh_posts):
            return state, []
        changes = _report(_FIRST_PROMPT.format(
            our_offer=our_offer or "our offer", name=name, limit=_FIRST_CHECK_MAX, **sources,
        ), "monitor_first_check")
        return state, changes[:_FIRST_CHECK_MAX]

    site_changed = bool(site) and state["site_hash"] != previous.get("site_hash")
    if not (site_changed or fresh_news or fresh_events or fresh_posts):
        return state, []
    return state, _report(_DIFF_PROMPT.format(
        our_offer=our_offer or "our offer", name=name,
        previous=previous.get("site_text") or "(none)",
        current=state["site_text"] if site_changed else "(unchanged)",
        **sources,
    ), "monitor_diff")
