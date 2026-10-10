"""Market-stage extraction and findings."""

from typing import Literal

from pydantic import Field, field_validator

from agents.schemas.coercion import LenientModel, none_str_to_null
from agents.schemas.offer import BuyerType, ProductCategory


class Pricing(LenientModel):
    tier: str = Field(description="")
    monthly_sub: str = Field(default=None ,description="")
    yearly_sub: str = Field(default=None ,description="")
    features: list[str] = Field(default_factory=list, description="")


class MarketExtraction(LenientModel):
    """Structured market definition + product-market fit output produced by the
    understand_market subgraph from the market interview (current web research +
    the product's own scraped material)."""

    buyer_type: BuyerType | None = Field(
        default=None, description="B2B, B2C, or both — who the buyer is"
    )
    category: ProductCategory | None = Field(
        default=None, description="The market/category the product operates in"
    )
    target_audience: str | None = Field(
        default=None, description="Who the product is for and the segments it serves"
    )
    pricing: list[Pricing] = Field(
        default_factory=list,
        description="Price tiers — from the product's own site/scraped content when present, otherwise suggested from current market rates",
    )
    pricing_source: Literal["site", "market_suggestion"] | None = Field(
        default=None,
        description="Where the pricing came from: the product's own site content or the agent's suggestion based on current market rates",
    )
    target_geo: list[str] = Field(
        default_factory=list,
        description="Geographies the product serves, prioritised by evidence from the site/scraped content, else market research",
    )
    category_conventions: str | None = Field(
        default=None,
        description="The conventions, norms, and expectations an offering in this category must meet to be credible (what 'good' looks like to buyers)",
    )
    market_demand: str | None = Field(
        default=None,
        description="Current demand level and readiness signals for the category — how much the market wants this, and evidence of that demand",
    )
    willingness_to_pay: str | None = Field(
        default=None,
        description="What buyers in the category are willing to pay / the budget norms that govern purchase decisions",
    )
    distribution_channels: list[str] = Field(
        default_factory=list,
        description="How the product is bought and sold in the category — direct sales, marketplace/platform, partnerships, retail, etc.",
    )
    adoption_barriers: list[str] = Field(
        default_factory=list,
        description="Obstacles standing between the target audience and adoption — cost, trust, switching, regulatory, awareness, etc.",
    )
    growth_outlook: Literal["growing", "stable", "declining", "unclear"] | None = Field(
        default=None,
        description="The category's current trajectory — is demand expanding, flat, shrinking, or unknown?",
    )
    market_fit: Literal["strong", "moderate", "weak", "unclear"] | None = Field(
        default=None, description="Product-market fit verdict for the product"
    )
    market_fit_reasoning: str | None = Field(
        default=None, description="Why that fit verdict was reached — evidence-based"
    )

    @field_validator("buyer_type", "category", "growth_outlook", mode="before")
    @classmethod
    def _coerce_enum_none(cls, v):
        if isinstance(v, str):
            v = none_str_to_null(v.strip().lower())
        return v


class MarketFindings(LenientModel):
    """Market research notes + concise product-market-fit understanding, from the market specialist."""

    findings: str = Field(description="Detailed markdown research notes defining the product's market and its product-market fit — the segment sizing, demand evidence, buyer types and current conditions the report section has to be built from")
    product_market_fit_understanding: str = Field(
        description="Brief understanding of how well the product fits its market; target 40 words, maximum 50"
    )
