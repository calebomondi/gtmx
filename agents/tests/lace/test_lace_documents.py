"""What the founder shares, as the Lace sees it: named in its prompt, and
read a part at a time."""

import json

from agents.lace.prompts import DOCUMENTS_LISTED, render_documents, system_prompt
from agents.lace.tools import DOCUMENT_PART_CHARS, build_tools
from agents.schemas.lace import DocumentSummary, LaceProfile


def _share(store, doc_id: str, filename: str, text: str, truncated: bool = False) -> None:
    store.shared[doc_id] = (DocumentSummary(id=doc_id, filename=filename, chars=len(text), truncated=truncated), text)


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


async def test_read_document_in_parts(store, settings):
    _share(store, "d1", "deck.pdf", "a" * DOCUMENT_PART_CHARS + "b" * 10, truncated=True)
    tools = {t.name: t for t in build_tools(store, settings)}
    first = await _run(tools["read_document"], document_id="d1")
    assert first["summary"] == "deck.pdf, part 1 of 2. Read part 2 next."
    assert first["data"]["text"] == "a" * DOCUMENT_PART_CHARS
    last = await _run(tools["read_document"], document_id="d1", part=2)
    assert last["data"]["text"] == "b" * 10 and "Only the start" in last["summary"]
    assert not (await _run(tools["read_document"], document_id="d1", part=3))["ok"]
    assert not (await _run(tools["read_document"], document_id="nope"))["ok"]
    listed = await _run(tools["list_documents"])
    assert [d["filename"] for d in listed["data"]] == ["deck.pdf"]


def test_the_prompt_names_shared_documents():
    docs = [DocumentSummary(id=f"d{i}", filename=f"doc{i}.pdf", chars=10) for i in range(DOCUMENTS_LISTED + 1)]
    listed = render_documents(docs)
    assert "- doc0.pdf (id d0)" in listed and "use list_documents" in listed
    prompt = system_prompt(LaceProfile(name="Ada", website="https://acme.test"), [], documents=[])
    assert "Documents the founder shared with you" in prompt and "None yet." in prompt
