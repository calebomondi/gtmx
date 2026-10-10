"""Refresh one competitor's social stats.

Profiles come from the socials the competitor agent recorded (unless graded
low confidence) plus any linked from the competitor's own homepage. Each
platform is scraped in parallel; a failed scrape keeps the last good profile
for the same URL so one Bright Data blip doesn't blank a card.
"""

from agents.concurrency import ContextThreadPoolExecutor
from agents.pipelines.web_utils import call_with_timeout
from data_sources.socials import profiles

_SCRAPE_TIMEOUT_S = 120  # Instagram scrapes measured at ~65s


def known_urls(tracking_sources: list[dict]) -> dict[str, str]:
    urls = {}
    for source in tracking_sources or []:
        kind = source.get("kind")
        if kind in profiles.PLATFORMS and source.get("confidence") != "low" and kind not in urls:
            url = profiles.profile_url(kind, source.get("value") or "")
            if url:
                urls[kind] = url
    return urls


def refresh(name: str, website: str | None, tracking_sources: list[dict],
            previous: dict | None) -> tuple[dict, dict[str, str]]:
    """Returns ({platform: profile}, {platform: url} newly found on the site)."""
    urls = known_urls(tracking_sources)
    found = {}
    if website and len(urls) < len(profiles.PLATFORMS):
        found = {p: u for p, u in profiles.find_on_site(website, name).items() if p not in urls}
        urls |= found
    if not urls:
        return {}, {}

    def fetch(item):
        platform, url = item
        return call_with_timeout(lambda: profiles.fetch(platform, url), _SCRAPE_TIMEOUT_S,
                                 default=None, label=f"socials[{platform}:{url}]")

    with ContextThreadPoolExecutor(max_workers=len(urls)) as pool:
        fetched = dict(zip(urls, pool.map(fetch, urls.items())))
    previous = previous or {}
    result = {}
    for platform, url in urls.items():
        profile = fetched[platform]
        if profile is None and (previous.get(platform) or {}).get("url") == url:
            profile = previous[platform]
        if profile is not None:
            result[platform] = profile
    return result, found
