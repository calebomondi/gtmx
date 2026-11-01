"""Laws, regulations, bills and filing obligations that apply to a startup,
in the places it is registered in and operates in. Found from official
sources, kept only when cited, and watched once the founder tracks them."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel

# Where a startup is registered or operates: an ISO 3166-1 alpha-2 country
# (KE), or an ISO 3166-2 subdivision where its laws differ (US-DE).
JURISDICTION_PATTERN = r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$"
JURISDICTION_MAX_LEN = 6

# law: an Act in force. regulation: rules made under one (legal notices,
# gazetted regulations). bill: a proposed law, still before parliament.
# obligation: something to file, register for or renew (a VAT return, a
# business permit), with dates of its own.
RegulationKind = Literal["law", "regulation", "bill", "obligation"]
REGULATION_KINDS: tuple[str, ...] = RegulationKind.__args__

# Where a bill is, in the order it gets there; the last three end it.
BillStage = Literal[
    "published", "first_reading", "committee", "second_reading", "whole_house", "third_reading",
    "assented", "withdrawn", "lapsed",
]
BILL_STAGES: tuple[str, ...] = BillStage.__args__

# suggested: found by a search, waiting for the founder to track or dismiss it.
# tracked: the Lace watches it and says when it changes.
RegulationStatus = Literal["suggested", "tracked", "dismissed"]
REGULATION_STATUSES: tuple[str, ...] = RegulationStatus.__args__


class RegulationQuery(LenientModel):
    jurisdiction: str = Field(description="The ISO code the search is for, as given, e.g. KE")
    query: str = Field(description="A specific web search, e.g. 'Kenya Data Protection Act data processor "
                                   "registration ODPC fintech'")


class RegulationPlan(LenientModel):
    queries: list[RegulationQuery] = Field(default_factory=list)


class Regulation(LenientModel):
    kind: RegulationKind
    title: str = Field(description="Its official name, e.g. 'The Data Protection Act, 2019' or 'VAT monthly return'")
    authority: str | None = Field(default=None, description="Who makes or enforces it: parliament, ministry, "
                                                            "regulator or tax authority")
    jurisdiction: str = Field(description="The ISO code of the place it applies in, one of those given")
    url: str = Field(description="The page that states it, copied exactly from the sources")
    stage: BillStage | None = Field(default=None, description="Bills only: how far through parliament, only if stated")
    in_force_on: str | None = Field(default=None, description="When it took or takes effect, YYYY-MM-DD, only if stated")
    next_date: str | None = Field(default=None, description="The next date that matters (a filing deadline, a "
                                                            "renewal, the close of public comment), YYYY-MM-DD, "
                                                            "only if stated")
    why_it_applies: str = Field(description="One sentence: what about this startup brings it under this, from its facts")
    what_to_do: str = Field(description="One sentence: the concrete step (register, file, renew, comment, watch)")
    relevance: Literal["strong", "moderate", "weak"] = Field(
        default="moderate",
        description="strong = plainly applies to what the startup does; weak = only a loose link",
    )


class RegulationList(LenientModel):
    regulations: list[Regulation] = Field(default_factory=list)


class RegulationSummary(Regulation):
    id: str
    status: RegulationStatus


class Jurisdiction(LenientModel):
    """Where the startup is registered and operates. Searched only once confirmed."""
    registered_in: str | None = None
    operates_in: list[str] = Field(default_factory=list)
    confirmed: bool = False

    @property
    def places(self) -> list[str]:
        """Every place, the registered one first, each once."""
        return list(dict.fromkeys([*([self.registered_in] if self.registered_in else []), *self.operates_in]))
