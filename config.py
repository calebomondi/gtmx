"""The single source of runtime configuration for every layer.

It lives at the repo root, not under backend/, because agents/ and
data_sources/ read it too and must not import backend/. Nothing else in the
codebase reads os.environ or .env: add a field here instead.

Field names are lowercase; pydantic-settings matches them to env vars
case-insensitively (`exa_api_key` <- EXA_API_KEY).
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- App --
    project_name: str = "GTMX (Go-To-Market Expert)"
    api_v1_str: str = "/api/v1"
    environment: str = "development"
    log_level: str = Field("INFO", validation_alias="GTMX_LOG_LEVEL")
    # Empty = same-origin only (dev proxy / reverse proxy). Comma-separated or a
    # JSON array, e.g. ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # -- Supabase --
    supabase_base_url: str = ""
    supabase_secret_key: str = ""
    supabase_db_conn_str: str = ""

    # -- LLM providers --
    dashscope_api_key: str = ""
    dashscope_base_url: str = ""
    openai_api_key: str = ""

    # -- Web data --
    exa_api_key: str = ""
    brightdata_api_key: str = ""
    composio_api_key: str = ""

    # -- Agent tuning --
    # How far back (days) research may look for sources. Kept short so the
    # analysis reflects CURRENT conditions, not history.
    market_recency_days: int = 365
    competitor_search_timeout_s: float = 20.0
    competitor_scrape_timeout_s: float = 30.0
    competitor_profile_workers: int = 6
    account_search_timeout_s: float = 20.0
    account_scrape_timeout_s: float = 30.0
    account_enrich_workers: int = 6
    account_socials_workers: int = 6
    account_search_cache_ttl: float = 600.0
    account_discovery_fast: bool = False
    account_discovery_strict_reachability: bool = False

    @computed_field
    @property
    def database_url(self) -> str:
        if self.environment == "development":
            return "sqlite+aiosqlite:///./blog.db"
        if not self.supabase_db_conn_str:
            raise ValueError("SUPABASE_DB_CONN_STR is required outside development")
        return self.supabase_db_conn_str

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [str(parsed).strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
