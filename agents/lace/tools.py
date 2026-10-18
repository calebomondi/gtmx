"""The Lace's tools, bound to one Lace's store.

Each tool returns a `ToolResult` as JSON. A failure is a result the model reads
and reasons about ("that page is down, try the pricing page"), so no tool error
ends the loop. Page text is capped before it reaches the model; the full page is
kept in the store.
"""

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Literal

from langchain_core.tools import BaseTool, tool

from agents.context_budget import _truncate_to_tokens, count_tokens
from agents.lace import icp as lace_icp
from agents.lace.store import JobRefused, LaceJobs, LaceStore
from agents.schemas.lace import Confidence, FactTopic, NewFact, SourcePage, ToolResult
from config import Settings
from data_sources.scraping import exa, firecrawl
from data_sources.scraping.firecrawl import FirecrawlError
from utils.log import logger

# Tokens of one page the model reads in full; a batch shares a smaller cap
# per page so eight pages can't flood the context.
PAGE_TOKEN_CAP = 3_000
BATCH_PAGE_TOKEN_CAP = 1_200
MAX_BATCH_PAGES = 8
MAX_MAP_LINKS = 60
SEARCH_RESULTS = 8
HIGHLIGHTS_PER_RESULT = 3
FACTS_PER_READ = 50
COMPETITORS_PER_READ = 50
# Facts the ICP is drawn from.
ICP_FACTS = 150


def _guarded(fn: Callable[..., Awaitable[ToolResult]]) -> Callable[..., Awaitable[str]]:
    """Serialise the result, and turn an unexpected exception into a failure
    the model can see, logged with the tool's name."""

    @wraps(fn)
    async def wrapper(*args, **kwargs) -> str:
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- reported to the model, logged here
            logger.exception("Lace tool %s failed", fn.__name__)
            result = ToolResult.failure(f"{fn.__name__} failed unexpectedly: {type(exc).__name__}")
        return result.model_dump_json(exclude_none=True)

    return wrapper


def _capped(markdown: str, cap: int) -> tuple[str, bool]:
    if count_tokens(markdown) <= cap:
        return markdown, False
    return _truncate_to_tokens(markdown, cap), True


def build_tools(store: LaceStore, settings: Settings, jobs: LaceJobs | None = None) -> list[BaseTool]:
    """Every tool the Lace can call, closed over its store. The job-starting
    tools are included only when there is something to run jobs."""

    @tool(parse_docstring=True)
    @_guarded
    async def search_web(
        query: str,
        depth: Literal["fast", "auto", "deep"] = "auto",
        published_after: str | None = None,
    ) -> ToolResult:
        """Search the web. Returns titles, URLs and highlights, not whole pages.

        Args:
            query: What to look for. Specific beats broad.
            depth: fast for a quick lookup, auto by default, deep for multi-step research (slower).
            published_after: ISO date (YYYY-MM-DD) to keep only recent sources.
        """
        try:
            results = await asyncio.to_thread(
                exa.search_highlights, query, settings,
                search_type=depth, num_results=SEARCH_RESULTS, start_published_date=published_after,
            )
        except TimeoutError as exc:
            return ToolResult.failure(str(exc))
        for r in results:
            r["highlights"] = r["highlights"][:HIGHLIGHTS_PER_RESULT]
        if not results:
            return ToolResult.success(f"No results for {query!r}.", [])
        return ToolResult.success(f"{len(results)} results for {query!r}.", results)

    @tool(parse_docstring=True)
    @_guarded
    async def map_site(url: str, search: str | None = None) -> ToolResult:
        """List the pages of a website, to choose which to read.

        Args:
            url: The site's address.
            search: Optional words to rank pages by, e.g. "pricing".
        """
        try:
            links = await asyncio.to_thread(firecrawl.map_site, url, settings, MAX_MAP_LINKS, search)
        except FirecrawlError as exc:
            return ToolResult.failure(str(exc))
        data = [{"url": l.url, "title": l.title} for l in links]
        return ToolResult.success(f"{len(data)} pages on {url}.", data)

    @tool(parse_docstring=True)
    @_guarded
    async def read_page(url: str) -> ToolResult:
        """Read one web page or document as markdown.

        Args:
            url: The page's address.
        """
        try:
            page = await asyncio.to_thread(firecrawl.scrape_page, url, settings)
        except FirecrawlError as exc:
            return ToolResult.failure(str(exc))
        await store.save_source(SourcePage(url=page.url, title=page.title, markdown=page.markdown))
        text, cut = _capped(page.markdown, PAGE_TOKEN_CAP)
        note = " (truncated)" if cut else ""
        return ToolResult.success(f"Read {page.url}{note}.", {"url": page.url, "title": page.title, "markdown": text})

    @tool(parse_docstring=True)
    @_guarded
    async def read_pages(urls: list[str]) -> ToolResult:
        """Read several pages at once (up to 8), each shortened. Cheaper than reading them one by one.

        Args:
            urls: The pages' addresses.
        """
        if not urls:
            return ToolResult.failure("No URLs given.")
        if len(urls) > MAX_BATCH_PAGES:
            return ToolResult.failure(f"At most {MAX_BATCH_PAGES} pages per call; got {len(urls)}.")
        try:
            pages, failures = await asyncio.to_thread(firecrawl.scrape_pages, urls, settings)
        except FirecrawlError as exc:
            return ToolResult.failure(str(exc))
        data = []
        for page in pages:
            await store.save_source(SourcePage(url=page.url, title=page.title, markdown=page.markdown))
            text, cut = _capped(page.markdown, BATCH_PAGE_TOKEN_CAP)
            data.append({"url": page.url, "title": page.title, "markdown": text, "truncated": cut})
        data += [{"url": f.url, "error": f.reason} for f in failures]
        return ToolResult(ok=bool(pages), summary=f"Read {len(pages)} of {len(urls)} pages.", data=data,
                          error=None if pages else "No page could be read.")

    @tool(parse_docstring=True)
    @_guarded
    async def get_facts(topic: FactTopic | None = None) -> ToolResult:
        """What you have recorded about the startup, newest first.

        Args:
            topic: Only facts on this topic; all topics when omitted.
        """
        facts = await store.facts(topic, FACTS_PER_READ)
        data = [{"id": f.id, "topic": f.topic, "claim": f.claim, "source_url": f.source_url,
                 "confidence": f.confidence, "origin": f.origin} for f in facts]
        return ToolResult.success(f"{len(data)} facts" + (f" on {topic}." if topic else "."), data)

    @tool(parse_docstring=True)
    @_guarded
    async def record_fact(
        topic: FactTopic,
        claim: str,
        source_url: str | None = None,
        confidence: Confidence = "medium",
        from_founder: bool = False,
        replaces_id: str | None = None,
    ) -> ToolResult:
        """Save something a source or the founder states about the startup, so you remember it in every later conversation. Not for your own opinions.

        Args:
            topic: What the fact is about.
            claim: One self-contained sentence.
            source_url: The page that states it. Required unless the founder told you.
            confidence: high when a source states it outright, low when you inferred it.
            from_founder: True when the founder told you this.
            replaces_id: The id of a fact this one corrects or updates.
        """
        claim = claim.strip()
        if not claim:
            return ToolResult.failure("The claim is empty.")
        if not source_url and not from_founder:
            return ToolResult.failure("A fact needs a source_url unless the founder told you.")
        fact = NewFact(topic=topic, claim=claim, source_url=source_url, confidence=confidence,
                       origin="user" if from_founder else "research", replaces_id=replaces_id)
        try:
            saved = await store.record_fact(fact)
        except KeyError:
            return ToolResult.failure(f"No fact with id {replaces_id!r} to replace.")
        return ToolResult.success(f"Recorded fact {saved.id}.", {"id": saved.id})

    @tool(parse_docstring=True)
    @_guarded
    async def list_competitors() -> ToolResult:
        """The competitors you are tracking for the startup, with what each one does."""
        rows = await store.competitors(COMPETITORS_PER_READ)
        data = [r.model_dump() for r in rows]
        return ToolResult.success(f"{len(data)} competitors tracked.", data)

    @tool(parse_docstring=True)
    @_guarded
    async def define_icp(guidance: str | None = None) -> ToolResult:
        """Work out (or rework) who the startup should sell to: its ideal customer profile, from everything you know. Do this before looking for customers, and again when the founder corrects who their buyers are (record their correction with record_fact first).

        Args:
            guidance: Optional direction from the founder, e.g. "focus on clinics in Nairobi".
        """
        profile, facts, rivals = await asyncio.gather(
            store.profile(), store.facts(None, ICP_FACTS), store.competitors(COMPETITORS_PER_READ))
        icp = await asyncio.to_thread(lace_icp.define_icp, profile, facts, rivals, guidance)
        await store.save_icp(icp)
        return ToolResult.success("Saved the ideal customer profile.", icp.model_dump(exclude_defaults=True))

    tools = [search_web, map_site, read_page, read_pages, get_facts, record_fact, list_competitors, define_icp]
    if jobs is None:
        return tools

    @tool(parse_docstring=True)
    @_guarded
    async def find_competitors(focus: str | None = None) -> ToolResult:
        """Start a thorough search for the startup's real competitors: it finds companies, checks each has a real website and competes for the same buyers, and profiles them with sources. Takes several minutes and runs in the background; you get an update when it is done. Use list_competitors for ones already found.

        Args:
            focus: Optional angle from the founder, e.g. "local players in Kenya" or "AI-first tools".
        """
        try:
            await jobs.start("find_competitors", {"focus": focus})
        except JobRefused as exc:
            return ToolResult.failure(str(exc))
        return ToolResult.success("Started the competitor search. It takes a few minutes; "
                                  "you will get an update here when it finishes.")

    @tool(parse_docstring=True)
    @_guarded
    async def check_competitors() -> ToolResult:
        """Check the tracked competitors now for moves that matter (pricing, product, positioning, funding, events, news) since the last check. Runs in the background; you get an update if anything material changed. They are also checked daily on their own."""
        try:
            await jobs.start("check_competitors", {})
        except JobRefused as exc:
            return ToolResult.failure(str(exc))
        return ToolResult.success("Started checking the competitors. You will get an update here if anything "
                                  "material changed.")

    return [*tools, find_competitors, check_competitors]
