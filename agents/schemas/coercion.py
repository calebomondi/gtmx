"""Validators that repair the habitual ways LLMs mangle structured output, so
pydantic can validate instead of forcing a costly re-ask."""

import json
from types import UnionType
from typing import Union, get_args, get_origin

from pydantic import BaseModel, model_validator


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


def _expects_container(annotation) -> bool:
    """True for list/dict/nested-model annotations, through Optional/Union."""
    origin = get_origin(annotation) or annotation  # bare `list`/`dict` have no origin
    if origin in (list, dict, tuple, set):
        return True
    if origin in (Union, UnionType):
        return any(_expects_container(arg) for arg in get_args(annotation) if arg is not type(None))
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


class LenientModel(BaseModel):
    """Base for every model an LLM fills. Any container field that arrived as a
    JSON string is parsed before validation -- the one repair, applied to every
    such field, instead of a per-field validator someone has to remember."""

    @model_validator(mode="before")
    @classmethod
    def _parse_serialized_containers(cls, data):
        if not isinstance(data, dict):
            return data
        repaired = dict(data)
        for name, field in cls.model_fields.items():
            key = field.alias or name
            value = repaired.get(key)
            if isinstance(value, str) and _expects_container(field.annotation):
                repaired[key] = coerce_json(value)
        return repaired
