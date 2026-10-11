"""Content-quality screening for scraped web bodies.

Exa serves pages from a cache. When a site is young, redesigned, or was previously a
placeholder, that cache can hold a stale snapshot: a live site returns a dead-site
body. Verified on https://shangalabs.com/ — a real agency site (68k of HTML, 5.7k
visible chars) whose cached scrape was a 400-char Squarespace parking page
("Coming Soon / We're under construction").

That failure mode is worse than an unreachable site. A dead URL fails loudly and the
intake interrupts to ask the user; a stale body is *truthy*, so it sails through the
length check in `discover_offer.scrape_website`, the run proceeds on boilerplate, and
the workspace reports `confirmed: True` having learned nothing. Worse, it reaches the
research stages through `search_and_scrape`, where "under construction" gets quoted as
evidence about the company.

So screening is deliberately separate from fetching. `scrape_url` forces a fresh crawl
(see `exa.py`) which fixes the cases we CAN refresh; this module catches what we still
cannot trust. The two are complementary, not redundant.
"""

from __future__ import annotations

import html

# Two floors, because the two call sites mean different things by "a body of text".
#
# A PRIMARY page (the user's own URL, gathered as the single source of truth for what
# their offer is) must be substantial: below this it cannot carry a description, a
# problem statement, or a list of capabilities — the three things intake exists to
# extract. Real service/product pages land in the thousands.
MIN_PAGE_CHARS = 800

# A SEARCH RESULT is a supplementary snippet, not the source of truth. Real hits are
# routinely short: a 580-char LinkedIn post and a 677-char company-directory entry are
# both genuine signal, and screening them out on length alone cost us two thirds of the
# result set on a live query. Kept only high enough to catch empty/truncated junk.
MIN_SEARCH_CHARS = 250

# Markers only decide a body that is ALSO short. A long page that merely says "coming
# soon" — a launch post, a newsletter, a changelog — is real content and must survive.
# The observed parking page was 400 chars, so this ceiling catches it while leaving
# genuine long-form prose alone.
PLACEHOLDER_MARKER_MAX_CHARS = 2000

# Dead-site / placeholder families, each observed on real pages in this project's
# own runs. Matched case-insensitively.
STALE_MARKERS: tuple[str, ...] = (
    "under construction",
    "coming soon",
    "check back",
    "temporarily unavailable",
    "parkingpage",
    "page not found",
    "site is being built",
    "launching soon",
)

# Repetition is the other reliable tell for a generated placeholder: the same line
# emitted repeatedly is a template, not prose.
_REPEAT_THRESHOLD = 3


def decode_entities(text: str) -> str:
    """Undo HTML entity escaping.

    Scraped bodies arrive inconsistently HTML-escaped. `Engineering & Innovation
    Consultancy` and `Engineering &amp; Innovation Consultancy` must compare equal,
    or name matching silently flips depending on which form Exa happened to return.
    """
    if "&" not in text:
        return text
    return html.unescape(text)


def _is_repetitive(text: str) -> bool:
    """True when the same substantial line recurs `_REPEAT_THRESHOLD`+ times AND
    those repeats account for a majority of the body — distinguishing a generated
    placeholder (which is mostly repeated filler) from a legitimate page that happens
    to repeat a trust badge or CTA line.
    """
    counts: dict[str, int] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 40:
            continue
        counts[line] = counts.get(line, 0) + 1
    total = sum(len(l) for l in text.splitlines() if len(l.strip()) >= 40)
    if total == 0:
        return False
    dominant = max(counts.values(), default=0)
    if dominant < _REPEAT_THRESHOLD:
        return False
    dominant_lines = max(counts.keys(), key=counts.get)
    share = counts[dominant_lines] * len(dominant_lines) / total
    return share > 0.5


def is_stale_body(text: str | None, min_chars: int = MIN_PAGE_CHARS) -> bool:
    """True when the body looks like a placeholder or dead page rather than content.

    `min_chars` is the caller's floor: MIN_PAGE_CHARS for a primary page,
    MIN_SEARCH_CHARS for a supplementary search snippet.
    """
    if not text:
        return True
    stripped = decode_entities(text).strip()
    if len(stripped) < min_chars:
        return True
    # Markers only count while the body is still small enough to BE a placeholder.
    # Past that ceiling a page mentioning "coming soon" is real content.
    if len(stripped) <= PLACEHOLDER_MARKER_MAX_CHARS:
        lowered = stripped.lower()
        if any(marker in lowered for marker in STALE_MARKERS):
            return True
    return _is_repetitive(stripped)


def is_usable_body(text: str | None, min_chars: int = MIN_PAGE_CHARS) -> bool:
    """True when the body is substantial enough and specific enough to research from."""
    return not is_stale_body(text, min_chars=min_chars)


def rejection_reason(text: str | None, min_chars: int = MIN_PAGE_CHARS) -> str:
    """Why `is_usable_body` said no — for logs and test failure messages."""
    if not text:
        return "empty"
    stripped = decode_entities(text).strip()
    if len(stripped) < min_chars:
        return f"too short ({len(stripped)} chars < {min_chars})"
    if len(stripped) <= PLACEHOLDER_MARKER_MAX_CHARS:
        lowered = stripped.lower()
        for marker in STALE_MARKERS:
            if marker in lowered:
                return f"placeholder marker {marker!r}"
    if _is_repetitive(stripped):
        return "repetitive template"
    return "unknown"