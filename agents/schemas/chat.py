"""The workspace chat agent's structured step."""

from pydantic import Field

from agents.schemas.coercion import LenientModel


class ChatResearchPlan(LenientModel):
    needs_web: bool = Field(
        default=False,
        description="True only when the question needs facts the workspace data cannot answer (recent news, a company not on the list, current prices)",
    )
    queries: list[str] = Field(
        default_factory=list,
        description="At most 2 focused web-search queries when needs_web is true; empty otherwise",
    )
