"""The Lace's database store: scoped to one Lace, facts superseded not
overwritten, sources upserted, and the constraints held by Postgres."""

import uuid

import psycopg
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.exc import IntegrityError

from agents.lace.graph import build_lace_graph
from agents.schemas.lace import NewFact, SourcePage
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services.errors import NotFoundError
from backend.app.services.lace_store import DbLaceStore
from config import settings


def _seed_lace(name: str = "Ada") -> uuid.UUID:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute(
            "INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, %s, 'https://acme.test') RETURNING id",
            (uuid.uuid4(), uuid.uuid4(), name),
        ).fetchone()[0]


@pytest.fixture
def store() -> DbLaceStore:
    return DbLaceStore(AsyncSessionLocal, _seed_lace())


def _fact(claim: str, topic="offer", **kw) -> NewFact:
    return NewFact(topic=topic, claim=claim, source_url="https://acme.test", **kw)


async def test_profile(store):
    profile = await store.profile()
    assert (profile.name, profile.website, profile.startup_name) == ("Ada", "https://acme.test", None)


async def test_profile_of_a_missing_lace():
    with pytest.raises(NotFoundError):
        await DbLaceStore(AsyncSessionLocal, uuid.uuid4()).profile()


async def test_facts_newest_first_and_by_topic(store):
    await store.record_fact(_fact("Sells payroll."))
    await store.record_fact(_fact("From $20 a month.", topic="pricing"))
    assert [f.claim for f in await store.facts()] == ["From $20 a month.", "Sells payroll."]
    assert [f.claim for f in await store.facts("pricing")] == ["From $20 a month."]
    assert len(await store.facts(limit=1)) == 1


async def test_superseded_fact_is_hidden_but_kept(store):
    old = await store.record_fact(_fact("From $15.", topic="pricing"))
    new = await store.record_fact(_fact("From $20.", topic="pricing", replaces_id=old.id))
    assert [f.id for f in await store.facts()] == [new.id]
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT superseded_by_id FROM lace_facts WHERE id = %s", (old.id,)).fetchone()[0] == uuid.UUID(new.id)


async def test_facts_are_scoped_to_their_lace(store):
    other = DbLaceStore(AsyncSessionLocal, _seed_lace("Bob"))
    theirs = await other.record_fact(_fact("Bob's secret."))
    assert await store.facts() == []
    # Not even by id: replacing another Lace's fact is "no such fact".
    with pytest.raises(KeyError):
        await store.record_fact(_fact("Hijack.", replaces_id=theirs.id))
    assert [f.claim for f in await other.facts()] == ["Bob's secret."]


async def test_replacing_a_malformed_id_is_no_such_fact(store):
    with pytest.raises(KeyError):
        await store.record_fact(_fact("x", replaces_id="not-a-uuid"))
    assert await store.facts() == []


async def test_database_refuses_an_unsourced_research_fact(store):
    with pytest.raises(IntegrityError, match="ck_lace_facts_sourced"):
        await store.record_fact(NewFact(topic="offer", claim="Trust me.", origin="research"))
    await store.record_fact(NewFact(topic="offer", claim="The founder said so.", origin="user"))


async def test_rereading_a_page_replaces_its_copy(store):
    await store.save_source(SourcePage(url="https://acme.test", title="v1", markdown="old"))
    await store.save_source(SourcePage(url="https://acme.test", title="v2", markdown="new"))
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute("SELECT title, content, content_hash FROM lace_sources").fetchall()
    assert len(rows) == 1 and rows[0][:2] == ("v2", "new") and len(rows[0][2]) == 64


async def test_lace_records_a_fact_through_the_database(store):
    replies = [
        AIMessage(content="", tool_calls=[{"name": "record_fact", "id": "c1", "args": {
            "topic": "pricing", "claim": "Plans start at $20.", "from_founder": True}}]),
        AIMessage(content="Noted."),
    ]
    graph = build_lace_graph(store, model_step=lambda messages, tools: replies.pop(0))
    out = await graph.ainvoke({"messages": [HumanMessage(content="we charge $20")]})
    assert out["messages"][-1].content == "Noted."
    [fact] = await store.facts()
    assert (fact.claim, fact.origin, fact.source_url) == ("Plans start at $20.", "user", None)
