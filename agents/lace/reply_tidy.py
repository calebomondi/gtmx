"""A reply's text, without the end the blocks under it already say. When the
Lace offers options as a choice (or a checklist, a form, or suggested
replies), models still tend to write the same options out as a list and ask
the same question again in text, so the founder reads everything twice.
Only the end of the reply is touched, and never all of it."""

import re

# Blocks that ask the founder something themselves.
QUESTION_BLOCKS = frozenset({"choices", "checklist", "form"})
# A suggestions block offers replies, but leaves asking to the text.
OFFER_BLOCKS = QUESTION_BLOCKS | {"suggestions"}

_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
# A sentence ending inside the line: then it says more than a question.
_SENTENCE_BREAK = re.compile(r"[.!?]\s+\S")


def _is_list_item(line: str) -> bool:
    return bool(_LIST_ITEM.match(line))


def _is_bare_question(line: str) -> bool:
    """One question and nothing else: no list marker, no sentence before it."""
    text = line.strip()
    return text.endswith("?") and not _is_list_item(text) and not _SENTENCE_BREAK.search(text[:-1])


def _skip_blank(lines: list[str], end: int) -> int:
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    return end


def without_repeated_options(reply: str, block_types: set[str]) -> str:
    """The reply without its closing options list (two or more items) and the
    lead-in to it ("Would you like me to:"), when a block under it offers
    them; under a question block, without the closing question too, since the
    block asks it. Unchanged when nothing under it offers options, or when
    trimming would leave nothing."""
    if not block_types & OFFER_BLOCKS:
        return reply
    asks = bool(block_types & QUESTION_BLOCKS)
    lines = reply.rstrip().split("\n")
    end = _skip_blank(lines, len(lines))
    questions = 0
    while asks and end > 0 and _is_bare_question(lines[end - 1]):
        end, questions = _skip_blank(lines, end - 1), questions + 1
    # The options: list items or, under a question block, one-question lines.
    start, items = end, 0
    while start > 0 and (_is_list_item(lines[start - 1]) or (asks and _is_bare_question(lines[start - 1]))):
        start, items = _skip_blank(lines, start - 1), items + 1
    if items >= 2 or questions >= 2:
        end = start
        lead_in = lines[end - 1].strip() if end > 0 else ""
        if lead_in.endswith((":", "?")) and not _SENTENCE_BREAK.search(lead_in[:-1]):
            end = _skip_blank(lines, end - 1)
    kept = "\n".join(lines[:end]).rstrip()
    return kept or reply
