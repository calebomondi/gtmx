"""Models for the Lace agent: what it knows, and what its tools return.

The Lace keeps its knowledge in the database. These are the shapes that cross
the boundary between the agent and the store the backend implements.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FactTopic = Literal[
    "company",      # who the startup is: name, location, team, stage
    "offer",        # what it sells, features, how it works
    "pricing",
    "customers",    # who buys today, named customers, case studies
    "market",
    "competition",
    "icp",
    "positioning",  # claims, differentiators, messaging
]
FACT_TOPICS: tuple[str, ...] = FactTopic.__args__

FactOrigin = Literal["crawl", "research", "user", "monitor"]
FACT_ORIGINS: tuple[str, ...] = FactOrigin.__args__
Confidence = Literal["high", "medium", "low"]
CONFIDENCES: tuple[str, ...] = Confidence.__args__


class NewFact(BaseModel):
    topic: FactTopic
    claim: str = Field(description="One self-contained sentence")
    source_url: str | None = Field(default=None, description="The page that states it; None for the founder's word")
    confidence: Confidence = "medium"
    origin: FactOrigin = "research"
    replaces_id: str | None = Field(default=None, description="A fact this one supersedes")


class Fact(NewFact):
    id: str
    recorded_at: datetime


class SourcePage(BaseModel):
    """A page the Lace read, kept so prompts can carry a summary instead."""
    url: str
    title: str = ""
    markdown: str


class LaceProfile(BaseModel):
    name: str
    website: str
    startup_name: str | None = None


class ToolResult(BaseModel):
    """What every Lace tool returns.

    `summary` is what the model reads first and must stand on its own; `data`
    carries the detail. A failure is a result too: the model reads the error
    and decides what to do, and the loop keeps running.
    """
    ok: bool
    summary: str
    data: Any = None
    error: str | None = None

    @classmethod
    def success(cls, summary: str, data: Any = None) -> "ToolResult":
        return cls(ok=True, summary=summary, data=data)

    @classmethod
    def failure(cls, error: str) -> "ToolResult":
        return cls(ok=False, summary=error, error=error)
