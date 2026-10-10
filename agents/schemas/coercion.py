"""Validators that repair the habitual ways LLMs mangle structured output, so
pydantic can validate instead of forcing a costly re-ask."""

import json


def coerce_json(value):
    """Parse a list/dict field that arrived as a JSON *string*.

    Weaker models double-serialise list fields (`tasks: '[{"id": ...}]'`), often
    wrapped in markdown fences or prose, or with stray characters after the
    closing bracket ('...] }'). Without this pydantic rejects the string and the
    caller falls into a full re-ask round-trip.

    Tries the whole string first, then the first complete JSON value starting at
    the EARLIEST bracket (so a top-level array beats the object brace inside it).
    Returns the parsed value only when it is a list or dict; anything else is
    returned unchanged for pydantic to judge.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text[:4].lower() == "json":
            text = text[4:].lstrip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, (list, dict)):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    decoder = json.JSONDecoder()
    positions = [p for p in (text.find("["), text.find("{")) if p != -1]
    idx = min(positions) if positions else -1
    while idx != -1:
        try:
            parsed, _ = decoder.raw_decode(text[idx:])
            if isinstance(parsed, (list, dict)):
                return parsed
        except json.JSONDecodeError:
            pass
        positions = [p for p in (text.find("[", idx + 1), text.find("{", idx + 1)) if p != -1]
        idx = min(positions) if positions else -1
    return value


def none_str_to_null(value):
    """LLMs often emit the literal strings 'None'/'N/A'/'null'/'nil'/'' for
    optional fields instead of a genuine null. Coerce those to None so enum or
    scalar validation doesn't reject them."""
    if isinstance(value, str) and value.strip().lower() in {"none", "n/a", "null", "nil", ""}:
        return None
    return value
