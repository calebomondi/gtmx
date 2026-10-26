import uuid

from pydantic import BaseModel


class UserResponse(BaseModel):
    """The verified Supabase user — identity comes from the token, not a local table."""

    id: uuid.UUID
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    in_pilot: bool = True
