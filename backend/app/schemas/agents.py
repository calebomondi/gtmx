from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from urllib.parse import urlparse


## Discovery Agent

class DiscoveryRequest(BaseModel):
    product_name: str = Field(description="")
    product_url: str = Field(description="")
    offer_description: Optional[str] = Field(default=None, description="User-written description for the manual (no-website) intake path")
    target_geo: Optional[list[str]] = Field(default=None, description="")
    # The user asserts this on the intake form rather than letting the agent
    # classify it. It drives the specialist roster (create_specialists
    # ._specialist_slots) and the offer_noun wording across the offer/market
    # interviews, so a wrong value is expensive downstream. The default keeps
    # older clients that send no offer_type behaving as before.
    source: Literal["website", "manual"] = Field(
        default="website",
        description="Whether the user provided a URL (website) or only a description (manual)",
    )
    offer_type: Literal["product", "service"] = Field(
        default="product",
        description="Whether the offer is a product (a thing bought/owned/used) or a service (work performed)",
    )

    @field_validator('product_url')
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            # Empty is allowed: the manual (no-website) intake path never uses it.
            return value
        parsed_url = urlparse(value)

        if parsed_url.scheme not in {'http', 'https'} or not parsed_url.hostname:
            raise ValueError('product_url must be a valid HTTP or HTTPS URL')

        return value

