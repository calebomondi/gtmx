"""What a Lace needs from the database, as an interface.

The backend implements this for one Lace and hands it to `build_lace_graph`,
so `agents/` never imports `backend/`. Every method is already scoped to that
Lace: no method takes a Lace or workspace id, which is what keeps the model from
reaching another startup's data whatever it asks for.
"""

from typing import Literal, Protocol

from agents.schemas.icp import ICP
from agents.schemas.opportunities import OpportunitySummary
from agents.schemas.lace import AccountSummary, CompetitorSummary, DocumentSummary, DraftSummary, Suggestions, Fact, FactTopic, LaceProfile, NewFact, SourcePage


class LaceStore(Protocol):
    async def profile(self) -> LaceProfile: ...

    async def facts(self, topic: FactTopic | None = None, limit: int = 50) -> list[Fact]:
        """Current facts (none that were superseded), newest first."""
        ...

    async def record_fact(self, fact: NewFact) -> Fact:
        """Store a fact. With `replaces_id`, the old fact is marked superseded,
        not deleted. Raises KeyError when `replaces_id` is not this Lace's."""
        ...

    async def set_startup_name(self, name: str) -> None: ...

    async def save_source(self, page: SourcePage) -> None:
        """Keep a page the Lace read; re-reading a URL replaces its copy."""
        ...

    async def icp(self) -> ICP | None: ...

    async def save_icp(self, icp: ICP) -> None:
        """Replace the Lace's ideal customer profile."""
        ...

    async def accounts(self, limit: int = 50) -> list[AccountSummary]:
        """Saved target accounts, strongest fit first."""
        ...

    async def opportunities(self, limit: int = 50) -> list[OpportunitySummary]:
        """Saved opportunities still open, the soonest deadline first."""
        ...

    async def competitors(self, limit: int = 50) -> list[CompetitorSummary]:
        """Saved (tracked) competitors, newest first."""
        ...

    async def suggestions(self, limit: int = 50) -> Suggestions:
        """What searches found that the founder has not saved or dismissed yet.
        Only saved items are worked from; these wait for the founder."""
        ...

    async def drafts(self, limit: int = 50) -> list[DraftSummary]:
        """Messages drafted and not yet sent, newest first."""
        ...

    async def documents(self, limit: int = 50) -> list[DocumentSummary]:
        """Documents the founder shared, newest first."""
        ...

    async def document_text(self, document_id: str) -> tuple[DocumentSummary, str] | None:
        """One shared document and its text; None when it is not this Lace's."""
        ...


JobKind = Literal["find_competitors", "check_competitors", "find_accounts", "find_contacts", "draft_outreach",
                  "find_opportunities", "define_icp"]


class JobRefused(Exception):
    """A background job could not start: one is already running, or a limit
    was reached. The message is said to the founder as is."""


class JobBlocked(Exception):
    """A job cannot do its work for a reason the founder can fix (not enough
    known yet, no ICP). The message is safe to say to them as is; any other
    failure is reported in general terms."""


class LaceJobs(Protocol):
    """Starts work too long for one turn. The job reports back by waking the
    Lace with an update when it is done."""

    async def start(self, kind: JobKind, params: dict) -> str:
        """The job's id. Raises JobRefused."""
        ...
