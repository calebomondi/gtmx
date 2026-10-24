"""What a Lace's reply can carry besides text: questions the founder answers
by clicking (a choice, a checklist, a short form) and cards for what it
found. Produced by its ask_* and show tools, attached to the reply they belong
to, and drawn by the frontend. The founder's answer is kept on their message,
so a question shows as answered whenever the conversation is read."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# What a card can show. The frontend picks the card's actions from its kind.
CardKind = Literal["competitor", "account", "opportunity", "draft"]
CARD_KINDS: tuple[str, ...] = CardKind.__args__


def new_block_id() -> str:
    return uuid.uuid4().hex[:12]


class ChoicesBlock(BaseModel):
    """A question with a few answers the founder can click instead of typing."""
    type: Literal["choices"] = "choices"
    # None on choices from before answers were kept: those can't be answered later.
    id: str | None = None
    question: str
    options: list[str]


class ChecklistItem(BaseModel):
    id: str = Field(description="What the item stands for, e.g. a saved item's id; comes back with the answer")
    label: str = Field(description="The item, in a few words")
    detail: str | None = Field(default=None, description="One short line under the label, e.g. why it's on the list")
    checked: bool = Field(default=True, description="Ticked to start with")


class ChecklistBlock(BaseModel):
    """Items the founder ticks or unticks, then submits: which to act on."""
    type: Literal["checklist"] = "checklist"
    id: str
    question: str
    items: list[ChecklistItem]
    submit: str


FieldKind = Literal["text", "long_text", "email", "url", "number"]
FIELD_KINDS: tuple[str, ...] = FieldKind.__args__


class FormField(BaseModel):
    name: str = Field(description="Key the answer comes back under, e.g. email")
    label: str = Field(description="What the founder sees, e.g. Their email")
    kind: FieldKind = "text"
    required: bool = True
    value: str | None = Field(default=None, description="Filled in to start with, when you already have a guess")


class FormBlock(BaseModel):
    """A few short fields the founder fills in, instead of typing a message."""
    type: Literal["form"] = "form"
    id: str
    question: str
    fields: list[FormField]
    submit: str


class CardBlock(BaseModel):
    """A snapshot of one saved item, by id: what it was when shown. Its
    actions act on the item as it is now."""
    type: Literal["card"] = "card"
    kind: CardKind
    id: str
    title: str
    subtitle: str | None = None
    body: str | None = None
    url: str | None = None
    # The item's status now (e.g. open, dismissed), filled in when the
    # conversation is read; "gone" when it no longer exists.
    status: str | None = None


class SuggestionsBlock(BaseModel):
    """Likely replies to a question the reply ends on, as chips the founder
    can tap to send. Not a question to answer: they can type anything."""
    type: Literal["suggestions"] = "suggestions"
    options: list[str]


class ActionBlock(BaseModel):
    """Something the Lace proposes doing in one of the founder's apps, with
    Approve and Decline. `status` is filled in when the conversation is read."""
    type: Literal["action"] = "action"
    id: str
    app: str
    title: str
    preview: str = ""
    status: str | None = None
    # What running it produced: a line, and a link to it when there is one.
    result: str | None = None
    url: str | None = None


UiBlock = Annotated[ChoicesBlock | ChecklistBlock | FormBlock | CardBlock | SuggestionsBlock | ActionBlock,
                    Field(discriminator="type")]


class BlockAnswer(BaseModel):
    """The founder's answer to a question under a reply."""
    block_id: str = Field(max_length=32)
    chosen: list[str] = Field(default_factory=list, max_length=50,
                              description="The option picked (a choice) or the ids ticked (a checklist)")
    values: dict[str, str] = Field(default_factory=dict, description="A form's answers, by field name")
