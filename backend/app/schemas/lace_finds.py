"""API shapes for a member's private finds and the team's review of them."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from agents.schemas.lace import SavedKind
from backend.app.schemas.laces import MessageAuthor

MAX_PUSH = 50
MAX_NOTE_CHARS = 500


class FindResponse(BaseModel):
    kind: SavedKind
    id: uuid.UUID
    name: str
    detail: str | None = Field(default=None, description="Its website, or an opportunity's organiser")
    status: str = Field(description="suggested, or saved (tracked / target / open) in the member's chat")
    proposed_at: datetime | None = Field(default=None, description="Pushed to the team, waiting for review")
    review_note: str | None = Field(default=None, description="Why it was sent back, when it was")
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
