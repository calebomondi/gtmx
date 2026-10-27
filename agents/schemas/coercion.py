"""Validators that repair the habitual ways LLMs mangle structured output, so
pydantic can validate instead of forcing a costly re-ask."""

import json
import re
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


def _list_item(annotation):
    """What a list field holds (through Optional), or None when it isn't a list."""
    if get_origin(annotation) in (Union, UnionType):
        lists = [_list_item(arg) for arg in get_args(annotation) if arg is not type(None)]
        return next((item for item in lists if item is not None), None)
    if get_origin(annotation) is list:
        args = get_args(annotation)
        return args[0] if args else str
    return None


_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")


def _as_text(item):
    """A list-of-text item that came as an object: its text, or its first text value."""
    if not isinstance(item, dict):
        return item
    text = item.get("text") or next((v for v in item.values() if isinstance(v, str) and v.strip()), None)
    return text if text is not None else item


def coerce_list(value, item):
    """A list field the model filled with prose, or (for a list of text) with
    objects. Prose becomes its lines for a list of text, and nothing for a list
    of objects, which need fields prose doesn't have."""
    if isinstance(value, str):
        if item is str:
            return [line for line in (_BULLET.sub("", raw).strip() for raw in value.splitlines()) if line]
        return [] if isinstance(item, type) and issubclass(item, BaseModel) else value
    if isinstance(value, list) and item is str:
        return [_as_text(v) for v in value]
    return value


class LenientModel(BaseModel):
    """Base for every model an LLM fills. Any container field that arrived as a
    JSON string is parsed before validation, and a list that came as prose (or
    a list of text that came as objects) is made a list -- the repairs, applied
    to every such field, instead of a per-field validator someone has to
    remember."""

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
                value = coerce_json(value)
            item = _list_item(field.annotation)
            if item is not None and key in repaired:
                value = coerce_list(value, item)
            if key in repaired:
                repaired[key] = value
        return repaired
