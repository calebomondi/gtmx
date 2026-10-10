"""The outreach agent's structured output."""

from pydantic import Field

from agents.schemas.coercion import LenientModel


class OutreachDraft(LenientModel):
    subject: str = Field(default="", description="Email subject line, under 8 words; empty for LinkedIn")
    body: str = Field(description="The message body, plain text")
