"""What a Lace's reply can carry besides text: buttons for the founder to
answer with, and cards for what it found. Produced by its ask_choice and show
tools, attached to the reply they belong to, and drawn by the frontend."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# What a card can show. The frontend picks the card's actions from its kind.
CardKind = Literal["competitor", "account", "opportunity", "draft"]
CARD_KINDS: tuple[str, ...] = CardKind.__args__


class ChoicesBlock(BaseModel):
    """A question with a few answers the founder can click instead of typing."""
    type: Literal["choices"] = "choices"
    question: str
    options: list[str]


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


UiBlock = Annotated[ChoicesBlock | CardBlock, Field(discriminator="type")]
