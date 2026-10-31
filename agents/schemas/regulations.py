"""Laws, regulations, bills and filing obligations that apply to a startup,
in the places it is registered in and operates in. Found from official
sources, kept only when cited, and watched once the founder tracks them."""

from typing import Literal

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
