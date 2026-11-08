"""GTM playbooks: each file is well formed and credits its sources, the
Lace's prompt lists them by name, and read_playbook hands over the method."""

import json

import pytest

from agents.lace.prompts import system_prompt
from agents.lace.tools import build_tools
from agents.prompts.playbook_library import PLAYBOOK_DIR, PlaybookError, parse, playbooks
from agents.schemas.lace import LaceProfile
from lace_fakes import MemoryStore

FIRST = {"cold-email", "follow-up", "reply-handling", "lead-temperature", "list-hygiene"}
# A playbook is read into a turn whole: long enough to teach, short enough to fit.
MAX_WORDS = 600


def test_every_playbook_is_well_formed_and_credited():
    found = playbooks()
    assert set(found) == FIRST
    for path in PLAYBOOK_DIR.glob("*.md"):
        book = found[path.stem]  # the file is named after the playbook
        assert book.use_when and book.body.startswith("# ")
        assert book.sources, f"{book.name} credits no source"
        assert len(book.body.split()) <= MAX_WORDS
        # Nothing a playbook teaches sends anything on its own.
        assert "click" in book.body or "approv" in book.body or book.name in ("lead-temperature",
                                                                             "list-hygiene")


def test_a_file_without_front_matter_is_refused():
    with pytest.raises(PlaybookError):
        parse("# Just a heading\n\nNo front matter.")
    with pytest.raises(PlaybookError):
        parse("---\nname: x\n---\nNo use_when line.")


def test_the_prompt_lists_each_playbook_by_name_and_use():
    prompt = system_prompt(LaceProfile(name="Ada", website="https://acme.test"), [])
    for book in playbooks().values():
        assert f"- {book.name}: {book.use_when}" in prompt
    # Only the index: the methods stay out until read.
    assert "## Before writing" not in prompt


async def test_read_playbook_hands_over_the_method(settings):
    tool = {t.name: t for t in build_tools(MemoryStore(), settings)}["read_playbook"]
    result = json.loads(await tool.ainvoke({"name": "Follow-up"}))
    assert result["ok"] and result["data"]["name"] == "follow-up"
    assert "At most two follow-ups" in result["data"]["method"]
    missing = json.loads(await tool.ainvoke({"name": "cold-call"}))
    assert not missing["ok"] and "cold-email" in missing["summary"]
