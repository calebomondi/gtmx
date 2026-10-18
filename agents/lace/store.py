"""What a Lace needs from the database, as an interface.

The backend implements this for one Lace and hands it to `build_lace_graph`,
so `agents/` never imports `backend/`. Every method is already scoped to that
Lace: no method takes a Lace or workspace id, which is what keeps the model from
reaching another startup's data whatever it asks for.
"""

from typing import Protocol

from agents.schemas.lace import Fact, FactTopic, LaceProfile, NewFact, SourcePage


class LaceStore(Protocol):
    async def profile(self) -> LaceProfile: ...

    async def facts(self, topic: FactTopic | None = None, limit: int = 50) -> list[Fact]:
        """Current facts (none that were superseded), newest first."""
        ...

    async def record_fact(self, fact: NewFact) -> Fact:
        """Store a fact. With `replaces_id`, the old fact is marked superseded,
        not deleted. Raises KeyError when `replaces_id` is not this Lace's."""
        ...

    async def save_source(self, page: SourcePage) -> None:
        """Keep a page the Lace read; re-reading a URL replaces its copy."""
        ...
