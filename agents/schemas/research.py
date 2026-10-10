"""The specialist team and the research-task plan every research stage executes."""

from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

from agents.schemas.coercion import coerce_json


class Specialist(BaseModel):
    domain: Literal["product", "service", "market", "competition", "gtm"] = Field(
        description="Which of the five research domains this specialist covers. 'product' or 'service' is the offer's own domain expert; the other three are market, competition and go-to-market. Required rather than inferred so a consumer can select the right specialist from a team without relying on list position -- without it, picking the product specialist out of OfferSessionState.specialists is guesswork.",
    )
    affiliation: str = Field(
        description="Primary affiliation of the specialist.",
    )
    name: str = Field(
        description="Name of the specialist."
    )
    role: str = Field(
        description="Role of the specialist in the context of the topic.",
    )
    description: str = Field(
        description="Description of the specialist focus, concerns, and motives.",
    )
    @property
    def persona(self) -> str:
        return (
            f"Name: {self.name}\n"
            f"Role: {self.role}\n"
            f"Domain: {self.domain}\n"
            f"Affiliation: {self.affiliation}\n"
            f"Description: {self.description}\n"
        )


class Perspectives(BaseModel):
    specialists: List[Specialist] = Field(
        description="Comprehensive list of the product/service specialist with their roles and affiliations.",
    )


class ResearchTask(BaseModel):
    area: str = Field(description="The knowledge-gap area this task closes")
    objective: str = Field(description="What this task must establish — a research goal, not a search string")
    queries: list[str] = Field(
        default_factory=list,
        description="2 independent web-search queries, ordered most specific first; the second is the broad fallback. NEVER include the offer's or brand's name — research the DOMAIN/CATEGORY the offer sits in, so the sources describe the category rather than the offer",
    )

    @field_validator("queries", mode="before")
    @classmethod
    def _coerce_queries(cls, v):
        v = coerce_json(v)
        if isinstance(v, list):
            return [q for q in v if isinstance(q, str)]
        return v  # not a list: let pydantic raise its own type error


class TaskList(BaseModel):
    tasks: list[ResearchTask] = Field(default_factory=list, description="The research tasks to execute this round")

    @field_validator("tasks", mode="before")
    @classmethod
    def _coerce_tasks(cls, v):
        return coerce_json(v)


class TaskResearchBundle(BaseModel):
    """What one research task actually retrieved.

    Held per task rather than as a single undifferentiated pile of documents,
    because `extract_evidence` evaluates one objective at a time: a task that
    came back empty is a real, reportable finding about that objective, and it
    would be invisible if its notes were merged with a task that succeeded.

    This is also why it replaces the old `context: list` accumulator rather than
    sitting alongside it — one copy of the research, associated with the task
    that produced it.
    """

    task_id: str = Field(default="", description="Which research task this bundle belongs to")
    area: str = Field(default="", description="The knowledge-gap area the task closed")
    objective: str = Field(default="", description="What the task set out to establish")
    round: int = Field(default=0, description="Which research round produced this bundle. Lets `extract_evidence` pick out the current round's bundles without relying on list position")
    queries: list[str] = Field(default_factory=list, description="The queries actually issued for this task")
    notes: str = Field(default="", description="The condensed source notes, in the <Document> shape the prompts already parse. Empty when the search failed")
    sources: list[str] = Field(default_factory=list, description="URLs actually retrieved for this task")
    search_failed: bool = Field(default=False, description="True when every query returned nothing usable")

    @field_validator("queries", "sources", mode="before")
    @classmethod
    def _coerce_bundle_lists(cls, v):
        if v is None:
            return []
        return coerce_json(v)
