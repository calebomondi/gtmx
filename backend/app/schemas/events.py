"""The app's event log: what users do in the customer app, by name from a
fixed list, and the admin views of it."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Every name the app may send. A new one is added here and in the frontend's
# lib/events.ts together; anything else is refused.
EventName = Literal[
    "page_viewed",  # detail: the page (and section), e.g. "lace_feed#opportunities"
    "setup_phase",  # detail: the phase a new Lace's setup reached
    "lace_settings_opened",
    "lace_people_opened",
    "chat_thread_switched",  # detail: team | mine
    "quick_ask_used",  # detail: the ask's label
    "contact_opened",  # detail: the channel, or none
    "search_opened",
    "feedback_opened",
]

MAX_EVENTS_PER_BATCH = 50


class EventIn(BaseModel):
    name: EventName
    detail: str | None = Field(default=None, max_length=64)
    lace_id: uuid.UUID | None = None
    at: datetime | None = Field(default=None, description="When it happened, by the browser's clock")


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=MAX_EVENTS_PER_BATCH)


class EventsRecorded(BaseModel):
    recorded: int = Field(description="Events kept; beyond the daily cap the rest are dropped")


class AdminEventRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    user_email: str | None = None
    lace_id: uuid.UUID | None
    lace_name: str | None = None
    name: str
    detail: str | None
    created_at: datetime


class EventCount(BaseModel):
    name: str
    detail: str | None
    count: int
    users: int


class EventDay(BaseModel):
    day: date
    count: int
    users: int


class EventSummary(BaseModel):
    days: int
    people: int = Field(description="Distinct people with any event in the window")
    totals: list[EventCount] = Field(description="Most frequent first")
    per_day: list[EventDay]
