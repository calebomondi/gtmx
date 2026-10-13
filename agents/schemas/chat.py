"""The workspace chat's structured step: who answers, and what they need."""

from typing import Literal

from pydantic import Field

from agents.schemas.coercion import LenientModel
from agents.schemas.outreach import Consultation

ChatDomain = Literal["product", "market", "competition", "gtm"]


class ChatRoute(LenientModel):
    lead: ChatDomain = Field(
        description="The specialist whose expertise the question is mainly about: product (what the offer is and does), "
                    "market (buyers, demand, pricing, sizing), competition (rivals, positioning, threats), "
                    "gtm (ICP, channels, accounts, messaging, outreach, launch plans)",
    )
    consult: list[Consultation] = Field(
        default_factory=list,
        description="At most 2 questions for OTHER specialists when a good answer also needs their expertise; empty otherwise",
    )
    needs_web: bool = Field(
        default=False,
        description="True only for facts the research cannot contain: recent news, a company not in the research, current prices or events",
    )
    queries: list[str] = Field(default_factory=list, description="At most 3 focused web-search queries when needs_web")


class ChatSuggestions(LenientModel):
    suggestions: list[str] = Field(
        default_factory=list,
        description="Exactly 3 short questions the user is likely to ask next, in their own voice, each under 12 words "
                    "and specific to this offer and conversation",
    )

