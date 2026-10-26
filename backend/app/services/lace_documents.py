"""Documents a founder shares with a Lace (a deck, a one-pager, a customer
list). Only the extracted text is kept, cut to a cap; the file is not stored.
The Lace sees them listed in its prompt and reads them with read_document."""

import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import DocumentSummary
from backend.app.database.lace_models import LaceDocument
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from config import settings
from data_sources import documents as parser

FILENAME_CHARS = 255
CONTENT_TYPE_CHARS = 127
_FALLBACK_TYPE = "application/octet-stream"


def summary(row: LaceDocument) -> DocumentSummary:
    return DocumentSummary(id=str(row.id), filename=row.filename, chars=len(row.text), truncated=row.truncated)


def max_bytes() -> int:
    return settings.lace_document_max_mb * 1024 * 1024


async def add(db: AsyncSession, lace_id: uuid.UUID, filename: str, content_type: str | None,
              data: bytes) -> LaceDocument:
    """Extract the text and keep it. InvalidInputError for a file too large,
    of a kind we don't read, or with no text; ConflictError past the cap."""
    filename = (filename or "document").strip()[:FILENAME_CHARS] or "document"
    if len(data) > max_bytes():
        raise InvalidInputError(f"{filename} is over {settings.lace_document_max_mb} MB.")
    held = await db.scalar(select(func.count()).select_from(LaceDocument).where(LaceDocument.lace_id == lace_id))
    if held >= settings.max_documents_per_lace:
        raise ConflictError(f"A Lace holds up to {settings.max_documents_per_lace} documents. Delete one first.")
    try:
        text = await asyncio.to_thread(parser.extract_text, filename, data)
    except (parser.UnsupportedDocument, parser.UnreadableDocument) as exc:
        raise InvalidInputError(str(exc)) from exc
    cap = settings.lace_document_max_chars
    row = LaceDocument(lace_id=lace_id, filename=filename, size_bytes=len(data), text=text[:cap],
                       truncated=len(text) > cap, content_type=(content_type or _FALLBACK_TYPE)[:CONTENT_TYPE_CHARS])
    db.add(row)
    await db.commit()
    return row


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, limit: int) -> list[LaceDocument]:
    return list((await db.scalars(select(LaceDocument).where(LaceDocument.lace_id == lace_id)
                                  .order_by(LaceDocument.created_at.desc()).limit(limit))).all())


async def get_in_lace(db: AsyncSession, lace_id: uuid.UUID, document_id: uuid.UUID) -> LaceDocument:
    row = await db.scalar(select(LaceDocument).where(LaceDocument.id == document_id, LaceDocument.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Document not found")
    return row


async def delete(db: AsyncSession, lace_id: uuid.UUID, document_id: uuid.UUID) -> None:
    await db.delete(await get_in_lace(db, lace_id, document_id))
    await db.commit()


async def attachments(db: AsyncSession, lace_id: uuid.UUID, ids: list[uuid.UUID]) -> list[LaceDocument]:
    """The documents a message carries, in the order given. NotFoundError if
    any is not this Lace's."""
    if not ids:
        return []
    if len(ids) > settings.max_documents_per_message:
        raise InvalidInputError(f"Attach up to {settings.max_documents_per_message} documents to a message.")
    rows = {row.id: row for row in (await db.scalars(select(LaceDocument).where(
        LaceDocument.lace_id == lace_id, LaceDocument.id.in_(ids)))).all()}
    if len(rows) < len(set(ids)):
        raise NotFoundError("Document not found")
    return [rows[i] for i in dict.fromkeys(ids)]
