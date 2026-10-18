"""The database behind one Lace: the `LaceStore` the agent's tools call.

Bound to a single Lace at construction, so every query is scoped to it and
nothing the model sends can widen that. Each call opens its own short session:
the agent may run several tool calls at once, and one AsyncSession must never
be shared across concurrent calls.
"""

import hashlib
import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.schemas.lace import Fact, FactTopic, LaceProfile, NewFact, SourcePage
from backend.app.database.lace_models import Lace, LaceFact, LaceSource
from backend.app.services.errors import NotFoundError


def _fact(row: LaceFact) -> Fact:
    return Fact(id=str(row.id), topic=row.topic, claim=row.claim, source_url=row.source_url,
                confidence=row.confidence, origin=row.origin, recorded_at=row.recorded_at)


def _parse_id(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


class DbLaceStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], lace_id: uuid.UUID):
        self._sessions = sessions
        self._lace_id = lace_id

    async def profile(self) -> LaceProfile:
        async with self._sessions() as session:
            lace = await session.get(Lace, self._lace_id)
        if lace is None:
            raise NotFoundError("Lace not found")
        return LaceProfile(name=lace.name, website=lace.website, startup_name=lace.startup_name)

    async def facts(self, topic: FactTopic | None = None, limit: int = 50) -> list[Fact]:
        query = (
            select(LaceFact)
            .where(LaceFact.lace_id == self._lace_id, LaceFact.superseded_by_id.is_(None))
            .order_by(LaceFact.recorded_at.desc())
            .limit(limit)
        )
        if topic is not None:
            query = query.where(LaceFact.topic == topic)
        async with self._sessions() as session:
            rows = (await session.scalars(query)).all()
        return [_fact(r) for r in rows]

    async def record_fact(self, fact: NewFact) -> Fact:
        async with self._sessions() as session, session.begin():
            replaced: LaceFact | None = None
            if fact.replaces_id is not None:
                replaced_id = _parse_id(fact.replaces_id)
                replaced = await session.scalar(
                    select(LaceFact).where(LaceFact.id == replaced_id, LaceFact.lace_id == self._lace_id)
                    .with_for_update()
                ) if replaced_id else None
                if replaced is None:
                    raise KeyError(fact.replaces_id)
            row = LaceFact(lace_id=self._lace_id, topic=fact.topic, claim=fact.claim,
                           source_url=fact.source_url, confidence=fact.confidence, origin=fact.origin)
            session.add(row)
            await session.flush()
            if replaced is not None:
                replaced.superseded_by_id = row.id
        return _fact(row)

    async def set_startup_name(self, name: str) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(update(Lace).where(Lace.id == self._lace_id).values(startup_name=name[:200]))

    async def save_source(self, page: SourcePage) -> None:
        digest = hashlib.sha256(page.markdown.encode()).hexdigest()
        stmt = insert(LaceSource).values(
            id=uuid.uuid4(), lace_id=self._lace_id, url=page.url, title=page.title,
            content=page.markdown, content_hash=digest,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_lace_sources_lace_id_url",
            set_={"title": stmt.excluded.title, "content": stmt.excluded.content,
                  "content_hash": stmt.excluded.content_hash, "fetched_at": stmt.excluded.fetched_at},
        )
        async with self._sessions() as session, session.begin():
            await session.execute(stmt)

