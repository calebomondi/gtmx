import json

from typing import Annotated, Optional

from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, NoDecode
from functools import lru_cache

from config import Config

cfg = Config()

class Settings(BaseSettings):
    #
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "GTMX (Go-To-Market Expert)"
    #
    ENVIRONMENT: str = "development"
    #
    # Mock signed-in user (auth is faked for now). Seeded into the users table
    # at startup and used for workspace ownership + the sidebar identity.
    MOCK_USER_EMAIL: str = "kalebmokua@gmail.com"
    MOCK_USER_NAME: str = "Caleb Mokua"
    #
    # CORS allow-list. Empty = same-origin only (recommended when the frontend
    # and API are served behind one host / reverse proxy). Comma-separated or
    # JSON-array values are both accepted, e.g.
    #   ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Origins allowed to call the API cross-origin",
    )
    #

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        if self.ENVIRONMENT == "development":
            return "sqlite+aiosqlite:///./blog.db"

        if not cfg.supabase_db_conn_str:
            raise ValueError("SUPABASE_DB_CONN_STR is required outside development")

        return cfg.supabase_db_conn_str

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()