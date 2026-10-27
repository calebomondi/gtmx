"""API shapes for a member's private finds and the team's review of them."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from agents.schemas.lace import SavedKind
from backend.app.schemas.laces import MessageAuthor

MAX_PUSH = 50
MAX_NOTE_CHARS = 500
MAX_NAME_CHARS = 255
MAX_SUMMARY_CHARS = 1000


class FindResponse(BaseModel):
    kind: SavedKind
    id: uuid.UUID
    name: str
    detail: str | None = Field(default=None, description="Its website, or an opportunity's organiser")
    status: str = Field(description="suggested, or saved (tracked / target / open) in the member's chat")
    proposed_at: datetime | None = Field(default=None, description="Pushed to the team, waiting for review")
    review_note: str | None = Field(default=None, description="Why it was sent back, when it was")
    summary: str | None = Field(default=None, description="What it is, or why it fits")
    link: str | None = Field(default=None, description="Its website, or the opportunity's page")
    push_note: str | None = Field(default=None, description="What the member who found it tells the reviewer")
    owner: MessageAuthor | None = Field(default=None, description="Who found it (in the team's review list)")
    can_review: bool | None = Field(default=None, description="Whether the viewer may approve it or send it back")


class FindRef(BaseModel):
    kind: SavedKind
    id: uuid.UUID


class PushRequest(BaseModel):
    items: list[FindRef] = Field(min_length=1, max_length=MAX_PUSH)


class PushResponse(BaseModel):
    pushed: int = Field(description="How many went up for review (others' and ones already waiting are skipped)")


class SendBackRequest(BaseModel):
    note: str | None = Field(default=None, max_length=MAX_NOTE_CHARS, description="Why, for the member who found it")


class FindEdit(BaseModel):
    """Only the fields sent change; null or blank clears a summary or note."""
    name: str | None = Field(default=None, max_length=MAX_NAME_CHARS)
    summary: str | None = Field(default=None, max_length=MAX_SUMMARY_CHARS)
    note: str | None = Field(default=None, max_length=MAX_NOTE_CHARS, description="For the reviewer, sent with a push")
