"""The database behind one Lace: the `LaceStore` the agent's tools call.

Bound to a single Lace at construction, so every query is scoped to it and
nothing the model sends can widen that. Each call opens its own short session:
the agent may run several tool calls at once, and one AsyncSession must never
be shared across concurrent calls.
"""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.schemas.icp import ICP
from agents.schemas.opportunities import OpportunitySummary
from agents.schemas.lace import AccountSummary, CompetitorSummary, ContactSummary, DocumentSummary, DraftSummary, Fact, ItemsChanged, NamedItem, NewContact, SavedKind, SavedVerdict, Suggestions, FactTopic, LaceProfile, NewFact, SourcePage
from backend.app.database.lace_models import Lace, LaceAccount, LaceCompetitor, LaceContact, LaceFact, LaceOutreach, LaceSource
from backend.app.services import lace_accounts, lace_competitors, lace_contacts, lace_documents, lace_opportunities, lace_outreach
from backend.app.services import laces as lace_service
from backend.app.services.errors import ConflictError, NotFoundError
from backend.app.services.laces import current_facts_query


def _fact(row: LaceFact) -> Fact:
    return Fact(id=str(row.id), topic=row.topic, claim=row.claim, source_url=row.source_url,
                confidence=row.confidence, origin=row.origin, recorded_at=row.recorded_at)


def _competitor(row: LaceCompetitor) -> CompetitorSummary:
    return CompetitorSummary(id=str(row.id), name=row.name, website=row.website, summary=row.summary,
                             origin=row.origin, status=row.status)


def _parse_id(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


# Status a saved item gets, per kind; removing sets every kind to dismissed.
_SAVED_STATUS = {"competitor": "tracked", "account": "target", "opportunity": "open"}
_SET_STATUS = {"competitor": lace_competitors.set_status, "account": lace_accounts.set_status,
               "opportunity": lace_opportunities.set_status}
_LIST = {"competitor": lace_competitors.list_for_lace, "account": lace_accounts.list_for_lace,
         "opportunity": lace_opportunities.list_for_lace}


def _name(row) -> str:
    return getattr(row, "title", None) or row.name


def _contact(contact: LaceContact, account: LaceAccount) -> ContactSummary:
    return ContactSummary(id=str(contact.id), name=contact.name, title=contact.title, email=contact.email,
                          linkedin=contact.linkedin, x=contact.x, instagram=contact.instagram,
                          facebook=contact.facebook, tiktok=contact.tiktok, company=account.name,
                          account_id=str(account.id), approved=contact.approved_at is not None)


def _draft(r: LaceOutreach) -> DraftSummary:
    return DraftSummary(id=str(r.id), channel=r.channel, company=r.recipient_company, subject=r.subject,
                        recipient=r.recipient_name or r.recipient_address or r.recipient_company, body=r.body)


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
        query = current_facts_query(self._lace_id, topic, limit)
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


    async def icp(self) -> ICP | None:
        async with self._sessions() as session:
            lace = await session.get(Lace, self._lace_id)
        return ICP.model_validate(lace.icp) if lace is not None and lace.icp else None

    async def save_icp(self, icp: ICP) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(update(Lace).where(Lace.id == self._lace_id).values(
                icp=icp.model_dump(mode="json"), icp_updated_at=datetime.now(UTC)))

    async def accounts(self, limit: int = 50) -> list[AccountSummary]:
        async with self._sessions() as session:
            rows = await lace_accounts.list_for_lace(session, self._lace_id, "target", limit)
        return [lace_accounts.summary(r) for r in rows]

    async def opportunities(self, limit: int = 50) -> list[OpportunitySummary]:
        async with self._sessions() as session:
            rows = await lace_opportunities.list_for_lace(session, self._lace_id, "open", limit)
        return [lace_opportunities.summary(r) for r in rows]

    async def competitors(self, limit: int = 50) -> list[CompetitorSummary]:
        async with self._sessions() as session:
            rows = await lace_competitors.list_tracked(session, self._lace_id, limit)
        return [_competitor(r) for r in rows]

    async def suggestions(self, limit: int = 50) -> Suggestions:
        async with self._sessions() as session:
            rivals = await lace_competitors.list_for_lace(session, self._lace_id, "suggested", limit)
            accounts = await lace_accounts.list_for_lace(session, self._lace_id, "suggested", limit)
            opportunities = await lace_opportunities.list_for_lace(session, self._lace_id, "suggested", limit)
        return Suggestions(competitors=[_competitor(r) for r in rivals],
                           accounts=[lace_accounts.summary(r) for r in accounts],
                           opportunities=[lace_opportunities.summary(r) for r in opportunities])

    async def drafts(self, limit: int = 50) -> list[DraftSummary]:
        async with self._sessions() as session:
            rows = await lace_outreach.drafts(session, self._lace_id, limit)
        return [_draft(r) for r in rows]

    async def documents(self, limit: int = 50) -> list[DocumentSummary]:
        async with self._sessions() as session:
            rows = await lace_documents.list_for_lace(session, self._lace_id, limit)
        return [lace_documents.summary(r) for r in rows]

    async def document_text(self, document_id: str) -> tuple[DocumentSummary, str] | None:
        doc_id = _parse_id(document_id)
        if doc_id is None:
            return None
        async with self._sessions() as session:
            try:
                row = await lace_documents.get_in_lace(session, self._lace_id, doc_id)
            except NotFoundError:
                return None
        return lace_documents.summary(row), row.text

    async def set_saved(self, kind: SavedKind, ids: list[str], verdict: SavedVerdict) -> ItemsChanged:
        status = _SAVED_STATUS[kind] if verdict == "save" else "dismissed"
        result = ItemsChanged()
        async with self._sessions() as session:
            for raw in ids:
                item_id = _parse_id(raw)
                try:
                    if item_id is None:
                        raise NotFoundError(raw)
                    row = await _SET_STATUS[kind](session, self._lace_id, item_id, status)
                except NotFoundError:
                    result.missing.append(raw)
                    continue
                result.changed.append(NamedItem(id=raw, name=_name(row)))
        return result

    async def removed(self, kind: SavedKind, limit: int = 50) -> list[NamedItem]:
        async with self._sessions() as session:
            rows = await _LIST[kind](session, self._lace_id, "dismissed", limit)
        return [NamedItem(id=str(r.id), name=_name(r)) for r in rows]

    async def retract_facts(self, ids: list[str]) -> ItemsChanged:
        result = ItemsChanged()
        async with self._sessions() as session:
            for raw in ids:
                fact_id = _parse_id(raw)
                try:
                    if fact_id is None:
                        raise NotFoundError(raw)
                    fact = await lace_service.review_fact(session, self._lace_id, fact_id, "retracted")
                except NotFoundError:
                    result.missing.append(raw)
                    continue
                result.changed.append(NamedItem(id=raw, name=fact.claim))
        return result

    async def contacts(self, limit: int = 100) -> list[ContactSummary]:
        async with self._sessions() as session:
            rows = await lace_contacts.list_for_lace(session, self._lace_id, limit)
        return [_contact(contact, account) for contact, account in rows]

    async def add_contact(self, contact: NewContact) -> ContactSummary:
        async with self._sessions() as session:
            account = await lace_accounts.founder_account(session, self._lace_id, contact.company, contact.website)
            row = await lace_contacts.add_named(session, self._lace_id, account, contact)
            return _contact(row, account)

    async def remove_contacts(self, ids: list[str]) -> ItemsChanged:
        parsed = {raw: _parse_id(raw) for raw in ids}
        async with self._sessions() as session:
            removed = await lace_contacts.remove(session, self._lace_id, [i for i in parsed.values() if i])
        gone = {str(contact_id): name for contact_id, name in removed}
        return ItemsChanged(changed=[NamedItem(id=raw, name=gone[str(i)]) for raw, i in parsed.items() if str(i) in gone],
                            missing=[raw for raw, i in parsed.items() if str(i) not in gone])

    async def edit_draft(self, draft_id: str, subject: str | None, body: str | None) -> DraftSummary:
        message_id = _parse_id(draft_id)
        changes = {k: v for k, v in (("subject", subject), ("body", body)) if v is not None}
        async with self._sessions() as session:
            try:
                if message_id is None:
                    raise NotFoundError(draft_id)
                message = await lace_outreach.get_in_lace(session, self._lace_id, message_id)
                return _draft(await lace_outreach.update(session, message, changes))
            except NotFoundError as exc:
                raise KeyError(draft_id) from exc
            except ConflictError as exc:
                raise ValueError(str(exc)) from exc

    async def discard_drafts(self, ids: list[str]) -> ItemsChanged:
        result = ItemsChanged()
        async with self._sessions() as session:
            for raw in ids:
                message_id = _parse_id(raw)
                try:
                    if message_id is None:
                        raise NotFoundError(raw)
                    message = await lace_outreach.get_in_lace(session, self._lace_id, message_id)
                    name = _draft(message).recipient
                    await lace_outreach.delete(session, message)
                except (NotFoundError, ConflictError):
                    result.missing.append(raw)
                    continue
                result.changed.append(NamedItem(id=raw, name=name))
        return result
