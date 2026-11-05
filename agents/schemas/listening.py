"""What social listening hears: each mention or comment, sorted by what it
means for the startup."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel

HeardKind = Literal["lead", "feedback", "question", "praise", "noise"]
HEARD_KINDS: tuple[str, ...] = HeardKind.__args__
# Where a Lace listens and reads posts from.
SocialPlatform = Literal["x", "instagram", "facebook", "tiktok", "linkedin"]
SOCIAL_PLATFORMS: tuple[str, ...] = SocialPlatform.__args__
# Where the founder is with something heard: still to act on, acted on, or set aside.
HeardStatus = Literal["new", "done", "dismissed"]
HEARD_STATUSES: tuple[str, ...] = HeardStatus.__args__


class HeardItem(LenientModel):
    ref: str = Field(description="The item's number, as listed")
    kind: HeardKind = Field(description="lead: may buy or partner; feedback: about the product or offer; "
                                        "question: asks something worth answering; praise; noise: the rest")
    note: str = Field(default="", description="In one line: why they could buy, the feedback, or the question")


class Heard(LenientModel):
    items: list[HeardItem] = Field(default_factory=list)
