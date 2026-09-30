"""Context assembly that fits the model's window.

Interview context accumulates via ``operator.add``: every turn files the pages
it just scraped, and the whole pile is re-sent on every subsequent call. A
typical scraped page is ~11k tokens of which the great majority is navigation,
cookie banners and unrelated prose, so an unbounded pile overruns the provider's
context window partway through an interview and kills the run.

Three mechanisms here keep it bounded without flattening the reasoning:

* :func:`count_tokens` / :func:`budget_context` — a hard ceiling with recency
  priority. The offer's own material is protected because the prompts call it
  authoritative; older search docs are dropped first.
* :func:`distill_document` — each scraped page is condensed *once*, at ingest,
  into a short query-relevant note. Because the note is computed once and kept,
  every later turn still has every source, just condensed.
* :func:`offer_brief` — the offer's own (multi-page, untruncated) scrape is
  condensed once and reused, instead of being re-embedded in full at every one
  of the ~11 prompt sites that quote it.

Token counts use ``cl100k_base`` as a proxy for the Qwen tokenizer. The exact
vocabulary differs by roughly ten percent either way, so the budget is set with
enough headroom that the estimate does not have to be exact.
"""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from utils.log import logger

from .llm.main import cheap_providers, invoke_structured_with_fallback

# -- On-disk cache persistence ------------------------------------------------
#
# The distill and offer-brief memo tables are pure functions of their inputs, so
# they survive across processes: writing each new entry through to disk turns
# repeated runs of the same offers (tests, prompt iteration) into near-free
# reruns. The cache is not a correctness path -- a stale or missing entry just
# costs a condensation call -- so persistence is deliberately best-effort: every
# failure is logged and swallowed, and a corrupted file simply reloads empty.
#
# Two caches get files so their keys (URLs vs name+body digests) never mingle.
_CACHE_DIR = Path(__file__).resolve().parent / ".cache"


def _load_cache_file(name: str) -> dict[str, str]:
    path = _CACHE_DIR / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, str)}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


# Serialises the read-modify-write of a dict set plus its file write-through.
# Distillation and offer_brief both run on thread pools, so without this two
# workers could interleave and drop entries on the disk snapshot.
_CACHE_LOCK = threading.Lock()


def _cache_set(name: str, store: dict, key: str, value: str) -> None:
    store[key] = value
    # Write-through each new entry. This rewrites the file per entry (O(n) per
    # write), which is a few milliseconds at this volume and buys crash safety:
    # a killed run keeps every entry it completed.
    try:
        with _CACHE_LOCK:
            path = _CACHE_DIR / f"{name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.warning("could not persist %s cache entry (%s); keeping in-memory only", name, exc)


# Condensing the same page twice is pure waste, and a run revisits sources
# across turns and subgraphs, so memoise on URL.
#
# URL-only keys (not url+focus): the original in-process cache is URL-keyed and
# the cross-run win of a persistent cache depends on the same URL reappearing,
# which happens across interviews and test reruns. The known simplification --
# focus-dependent condensation, first focus wins -- is inherited from that
# in-process design and now spans processes.
_DISTILL_CACHE: dict[str, str] = _load_cache_file("distill")

# The provider rejects prompts past 196,608 tokens. This leaves ample room for
# the conversation transcript, the instruction blocks, and the completion, all
# of which are counted against the same window.
DEFAULT_CONTEXT_BUDGET = 60_000

# The offer's own material is what the prompts describe as authoritative, so it
# gets a guaranteed share of the budget before any search doc competes for it.
OFFER_MATERIAL_SHARE = 0.25

# Below this, a partial document isn't worth including — a fragment too short to
# carry a claim is just noise that still costs a citation the model may invent.
MIN_PARTIAL_TOKENS = 400

# Target size for one distilled document. Three docs per turn, ~14 turns: at
# this size the whole interview's sources fit inside the budget comfortably.
DISTILL_TOKEN_TARGET = 1_200

# A condensed page still has to stay recognisable so the model can cite it.
DISTILL_HARD_CAP = 1_800

# Ceiling on concurrent page condenses. One search returns at most
# `num_results` (currently 3) docs, so this is a guard against a future larger
# result set rather than a tuning knob: unbounded fan-out against one provider
# account is how you get throttled mid-run.
_DISTILL_MAX_WORKERS = 4

TRUNCATION_MARKER = "\n\n[... truncated to fit the model's context window ...]"

_SEPARATOR = "\n\n---\n\n"

_ENCODER = None
_ENCODER_RESOLVED = False


def _encoder():
    """Load the tiktoken encoding once, or None if unavailable.

    tiktoken fetches its BPE table on first use, so a machine without network
    access to that download has to fall back to the character estimate below
    rather than fail the run.
    """
    global _ENCODER, _ENCODER_RESOLVED
    if _ENCODER_RESOLVED:
        return _ENCODER
    _ENCODER_RESOLVED = True
    try:
        import tiktoken

        _ENCODER = tiktoken.get_encoding("cl100k_base")
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning(
            "tiktoken unavailable (%s); falling back to a ~4-chars-per-token estimate",
            exc,
        )
        _ENCODER = None
    return _ENCODER


def count_tokens(text: str | None) -> int:
    """Approximate token count. Never raises; empty input is 0."""
    if not text:
        return 0
    enc = _encoder()
    if enc is not None:
        try:
            # disallowed_special=() keeps literal <|endoftext|>-style markers
            # that appear in scraped page text from raising.
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    return max(1, len(text) // 4)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    if not text:
        return ""
    if count_tokens(text) <= max_tokens:
        return text
    # The marker is appended to the truncated text, so it has to come out of the
    # allowance or every truncation lands just over the ceiling.
    room = max(1, max_tokens - count_tokens(TRUNCATION_MARKER))
    enc = _encoder()
    if enc is not None:
        try:
            ids = enc.encode(text, disallowed_special=())
            return enc.decode(ids[:room]) + TRUNCATION_MARKER
        except Exception:
            pass
    return text[: room * 4] + TRUNCATION_MARKER


def _render(chunks: list[str]) -> str:
    return _SEPARATOR.join(chunks)


def _drop_notice(n: int) -> str:
    return (
        f"[Note: {n} older source document(s) were omitted to fit the context window. "
        f"Do not cite or reference them — answer only from the documents shown above.]"
    )


def budget_context(
    context,
    budget_tokens: int = DEFAULT_CONTEXT_BUDGET,
    label: str = "context",
) -> str:
    """Render accumulated context chunks into one block that fits the window.

    The first chunk is the offer's own material (seeded by ``seed_product_context``
    and described by the prompts as authoritative), so it is capped generously
    but never dropped. The remaining chunks are search documents, kept newest
    first so the sources most relevant to where the interview has got to survive.

    When documents are dropped the model is told, because the prompts require it
    to list its sources and it should not cite a page it can no longer see.
    """
    if isinstance(context, str):
        context = [context]
    chunks = [c for c in (context or []) if c and c.strip()]
    if not chunks:
        return ""

    rendered = _render(chunks)
    total = count_tokens(rendered)
    if total <= budget_tokens:
        return rendered

    if len(chunks) == 1:
        # Nothing else to protect, so the whole budget is available to it.
        return _truncate_to_tokens(chunks[0], budget_tokens)

    # Reserve up front for the notice and the separators, so the assembled block
    # lands inside the budget rather than just past it.
    reserve = count_tokens(_drop_notice(1)) + 8 * (len(chunks) + 1)
    usable = max(budget_tokens - reserve, 1_000)

    kept_own = _truncate_to_tokens(chunks[0], int(usable * OFFER_MATERIAL_SHARE))
    spent = count_tokens(kept_own)

    kept: list[str] = []
    dropped = 0
    for chunk in reversed(chunks[1:]):
        cost = count_tokens(chunk)
        if spent + cost <= usable:
            kept.append(chunk)
            spent += cost
            continue
        # Newest doc that doesn't fit whole: take the portion that remains, then
        # stop — everything older is less relevant by definition.
        room = usable - spent
        if room > MIN_PARTIAL_TOKENS:
            part = _truncate_to_tokens(chunk, room)
            if count_tokens(part) > MIN_PARTIAL_TOKENS:
                kept.append(part)
                spent += count_tokens(part)
        dropped += 1
        break

    kept.reverse()
    dropped += len(chunks) - 1 - len(kept)

    # Separator and notice overhead are estimates; enforce the ceiling for real
    # by shedding the oldest surviving document until the block actually fits.
    while True:
        notice = _drop_notice(dropped) if dropped else ""
        parts = [kept_own, *kept, *( [notice] if notice else [] )]
        if count_tokens(_render(parts)) <= budget_tokens or not kept:
            break
        kept.pop(0)
        dropped += 1

    result = _render(parts)
    logger.info(
        "%s budgeted: %d chunks / %d tokens -> %d chunks / %d tokens (budget %d, dropped %d)",
        label, len(chunks), total, len(parts), count_tokens(result), budget_tokens, dropped,
    )
    return result


# ---------------------------------------------------------------------------
# Distillation
# ---------------------------------------------------------------------------

_DISTILL_SYSTEM = """You condense a scraped web page into a short, dense research note.

Extract only what is useful for analysing this topic:
{focus}

Write the note using these rules:
- Lead with the specific, checkable claims: mechanisms, numbers, latencies, limits, named systems, dates, comparisons.
- Keep concrete terminology and proper nouns exactly as written — they are what later sections cite.
- Drop navigation, boilerplate, cookie notices, marketing filler, and anything unrelated to the focus.
- Never invent. If the page does not support a claim, leave it out.
- Aim for roughly {target} tokens. Plain prose or tight bullets. No preamble, no heading, no closing summary.

Return only the note."""


def _doc_block(title: str, url: str, body: str) -> str:
    """Render in the same <Document> shape the interview prompts already parse."""
    return f'<Document href="{url}"/>\n{title}\n-----\n{body}\n</Document>'


def distill_document(
    doc: dict,
    focus: str,
    target_tokens: int = DISTILL_TOKEN_TARGET,
    log_label: str = "distill_document",
) -> str:
    """Condense one scraped page into a bounded note, memoised on its URL.

    A condensed page is strictly more useful than a truncated one: the summary
    is written against the current question, so the useful material survives
    even though the tail of the article does not.
    """
    url = (doc.get("url") or "").strip()
    title = (doc.get("title") or "").strip() or url
    text = doc.get("text") or ""

    if url and url in _DISTILL_CACHE:
        return _DISTILL_CACHE[url]

    if not text.strip():
        block = _doc_block(title, url or "unknown", "")
        if url:
            _cache_set("distill", _DISTILL_CACHE, url, block)
        return block

    # Short pages are already cheaper to keep than to condense, and sending
    # them through the model would cost a call to save nothing.
    if count_tokens(text) <= target_tokens:
        block = _doc_block(title, url or "unknown", text)
        if url:
            _cache_set("distill", _DISTILL_CACHE, url, block)
        return block

    try:
        note = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=_DISTILL_SYSTEM.format(focus=focus, target=target_tokens)),
                HumanMessage(content=f"PAGE TITLE: {title}\nURL: {url}\n\n{text}"),
            ],
            log_label=log_label,
            providers=cheap_providers(),
            thinking=False,
        )
    except Exception as exc:
        # Condensing is an optimisation, not a requirement. If it fails, fall
        # back to the head of the page so the run keeps its source at all.
        logger.warning("%s failed for %s (%s); keeping page head instead", log_label, url, exc)
        block = _doc_block(title, url or "unknown", _truncate_to_tokens(text, DISTILL_HARD_CAP))
        if url:
            _cache_set("distill", _DISTILL_CACHE, url, block)
        return block

    note = (note or "").strip() or _truncate_to_tokens(text, DISTILL_HARD_CAP)
    block = _doc_block(title, url or "unknown", _truncate_to_tokens(note, DISTILL_HARD_CAP))
    if url:
        _cache_set("distill", _DISTILL_CACHE, url, block)
    return block


def distill_documents(
    docs: list[dict],
    focus: str,
    log_label: str = "distill_document",
) -> str:
    """Condense a search result set concurrently, preserving document order.

    The pages in one search result set are independent of each other, but the
    call sites were a lazy generator consumed by str.join, which is strictly
    serial: three pages meant three back-to-back model round-trips where one
    wall-clock window would do. distill_document is sync, so this fans out over a
    thread pool rather than asyncio.

    Order is preserved deliberately -- the note order is what the answering
    model sees, and reordering sources between runs would make the same query
    produce differently-ordered context.
    """
    if not docs:
        return ""
    if len(docs) == 1:
        return distill_document(docs[0], focus=focus, log_label=log_label)

    workers = min(len(docs), _DISTILL_MAX_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        notes = list(
            pool.map(
                lambda doc: distill_document(
                    doc, focus=focus, log_label=log_label
                ),
                docs,
            )
        )
    return "\n\n---\n\n".join(notes)


_OFFER_BRIEF_SYSTEM = """You condense a scraped company/product page into a dense factual brief.

Write the brief using these rules:
- Lead with what the product IS, how it works mechanically, who it is for, and what it claims.
- Keep concrete claims, numbers, named technologies and differentiators exactly as written.
- Keep the substance a domain expert would need to judge the product seriously.
- Drop navigation, boilerplate, cookie notices, marketing filler and repeated CTAs.
- Never invent. If a claim is not on the page, leave it out.
- Aim for roughly {target} tokens. Plain prose or tight bullets. No preamble, no heading.

Return only the brief."""


_OFFER_BRIEF_CACHE: dict[str, str] = _load_cache_file("offer_brief")


def offer_brief(
    name: str,
    body: str,
    target_tokens: int = 1_500,
) -> str:
    """Condense the offer's own scrape once and memoise it.

    The scrape spans subpages and is deliberately never truncated at gather time,
    so it is routinely tens of thousands of tokens — and it is quoted at roughly
    three prompt sites per interview turn. Condensing it once removes that cost
    from every subsequent call without losing the grounding the interview needs.
    """
    body = (body or "").strip()
    if not body:
        return ""

    digest = hashlib.sha256(f"{name}\x00{body}".encode()).hexdigest()
    cached = _OFFER_BRIEF_CACHE.get(digest)
    if cached is not None:
        return cached

    if count_tokens(body) <= target_tokens:
        brief = body
    else:
        try:
            brief = invoke_structured_with_fallback(
                messages=[
                    SystemMessage(content=_OFFER_BRIEF_SYSTEM.format(target=target_tokens)),
                    HumanMessage(content=f"PRODUCT/SERVICE: {name}\n\n{body}"),
                ],
                log_label="offer_brief",
                providers=cheap_providers(),
                thinking=False,
            )
        except Exception as exc:
            logger.warning("offer_brief failed for %s (%s); keeping head instead", name, exc)
            brief = _truncate_to_tokens(body, DISTILL_HARD_CAP)
        brief = (brief or "").strip() or _truncate_to_tokens(body, DISTILL_HARD_CAP)

    _cache_set("offer_brief", _OFFER_BRIEF_CACHE, digest, brief)
    logger.info(
        "offer_brief for %r: %d tokens -> %d tokens",
        name, count_tokens(body), count_tokens(brief),
    )
    return brief
