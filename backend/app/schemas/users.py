import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, EmailStr

# Shared fields for user input
class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=120)

# Request body for creating a user (no extra fields needed)
class UserCreate(UserBase):
    avatar_url: str | None = Field(default=None, min_length=1, max_length=200)

# Update User
class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, min_length=1, max_length=200)

# Response body for returning a user to the client
class UserResponse(UserBase):
    # Allows creating schema directly from ORM model instances
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    avatar_url: str | None
    joined: datetime
    last_activity: datetime
