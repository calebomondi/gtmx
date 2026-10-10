"""The offer itself: what is being sold, as intake and the offer stage capture it."""

import operator
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class ProductCategory(str, Enum):
    SAAS = "saas"
    PAAS = "paas"
    IAAS = "iaas"
    MARKETPLACE = "marketplace"
    HARDWARE = "hardware"
    SERVICE = "service"
    AGENCY = "agency"
    CONSULTING = "consulting"
    OTHER = "other"


class BuyerType(str, Enum):
    B2B = "b2b"
    B2C = "b2c"
    BOTH = "both"


class FollowUp(BaseModel):
    # -------
    follow_up_question: Optional[str] = Field(
        default=None,
        description="Question to ask the user for any still-missing field; None once company_name, product_name, and product_desc are all provided",
    )
    user_replies: Annotated[list[str], operator.add] = Field(
        default_factory=list,
        description="Accumulated answers to follow_up_question from the user",
    )


class SnapshotFeature(BaseModel):
    """A feature as mentioned so far in the conversation. All fields optional
    because this is a PARTIAL, evolving capture — never a finalized profile."""

    name: str | None = None
    description: str | None = None
    differentiator: str | None = None


class OfferDataSnapshot(BaseModel):
    """Running, partial understanding of the product gathered progressively
    during the conversation. Everything is optional: unknown fields may be null
    or empty. Merged into state.product_data_snapshot on every capture turn
    (known values are never clobbered by thinner later captures)."""
    # Offer (Product/Service)
    company_name: str | None = None
    offer_name: str | None = None
    offer_description: str | None = None
    website_url: str | None = None
    intent: str | None = None
    target_geo: list[str] = Field(default_factory=list)
    problem_solved: str | None = Field(default=None, description="...")
    features: list[SnapshotFeature] = Field(default_factory=list)
    service_uniqueness: list[SnapshotFeature] = Field(default_factory=list, description="For a service: the distinctive elements that make this service different from alternatives")
    how_it_works: str | None = Field(default=None, description="How the product works end-to-end, in plain terms")


class ProductFindings(BaseModel):
    """Domain research notes + concise product-domain understanding, from the product specialist.

    Deliberately notes rather than the finished report section. A specialist that
    writes its own section in isolation cannot know what the market and
    competition specialists go on to find, so independently-written sections
    routinely restate each other or quietly contradict each other. The prose is
    composed once at the end by a single writer that can see all three sets of
    notes at once.
    """

    findings: str = Field(description="Detailed markdown research notes grounding the product in its domain/category — the evidence, terminology, named systems, limits and numbers the report section has to be built from")
    product_domain_understanding: str = Field(
        description="Brief understanding of how the product fits into its domain/category; target 40 words, maximum 50"
    )
