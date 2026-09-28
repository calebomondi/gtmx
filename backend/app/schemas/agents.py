from pydantic import BaseModel, Field, field_validator
from typing import Optional
from urllib.parse import urlparse


## Discovery Agent

class DiscoveryRequest(BaseModel):
    product_name: str = Field(description="")
    product_url: str = Field(description="")
    target_geo: Optional[list[str]] = Field(default=None, description="")

    @field_validator('product_url')
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        parsed_url = urlparse(value)

        if parsed_url.scheme not in {'http', 'https'} or not parsed_url.hostname:
            raise ValueError('product_url must be a valid HTTP or HTTPS URL')

        return value

