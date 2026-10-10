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
    # Emails granted the admin role at startup (idempotent). Further admins are
    # granted from the admin dashboard.
    admin_bootstrap_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # -- Supabase --
    supabase_base_url: str = ""
    supabase_secret_key: str = ""

    # -- Database --
    # Postgres everywhere. The default is the docker-compose.yml service; in
    # prod, point DATABASE_URL at Supabase Postgres (its plain postgresql:// URI).
    database_url: str = "postgresql://gtmx:gtmx@localhost:5432/gtmx"

    # -- LLM providers --
    dashscope_api_key: str = ""
    dashscope_base_url: str = ""
    openai_api_key: str = ""
    # Qwen models, tried in order (comma-separated in env). `llm_models` serves
    # reasoning calls; `llm_cheap_models` the bulk extraction/condensing calls.
    # qwen3.8-flash because qwen3.8-max's quota is exhausted on this account
    # (2026-10-10); switch back via env once it is funded.
    llm_models: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["qwen3.8-flash"])
    llm_cheap_models: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["qwen3.8-flash"])

    # -- Web data --
    exa_api_key: str = ""
    brightdata_api_key: str = ""
    composio_api_key: str = ""

    # -- Runs --
    # Wall-clock cap on one active segment of a run (time spent waiting for a
    # user's answer does not count: no task is alive then).
    discovery_segment_timeout_s: float = 1800.0

    # -- Usage limits (per user) --
    max_active_discovery_runs: int = 1
    max_discovery_runs_per_day: int = 10
    max_competitor_runs_per_day: int = 20
    max_account_runs_per_day: int = 20
    max_requests_per_minute: int = 120

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
    def sqlalchemy_database_url(self) -> str:
        """`database_url` with the async psycopg driver SQLAlchemy needs."""
        return "postgresql+psycopg://" + self.database_url.split("://", 1)[1]

    @field_validator("database_url")
    @classmethod
    def _require_postgres(cls, value: str) -> str:
        """Accept any Postgres URI form and store the plain libpq one, which
        psycopg (checkpointer) uses as-is and SQLAlchemy gets via
        `sqlalchemy_database_url`."""
        scheme, sep, rest = value.strip().partition("://")
        if not sep or scheme.split("+", 1)[0] not in ("postgresql", "postgres"):
            raise ValueError(
                f"DATABASE_URL must be a Postgres URI (got scheme {scheme!r}); "
                "SQLite is no longer supported. Run `docker compose up -d`."
            )
        return f"postgresql://{rest}"

    @field_validator("llm_models", "llm_cheap_models")
    @classmethod
    def _require_models(cls, value: list[str]) -> list[str]:
        # Fail at startup, not on the first LLM call of some user's run.
        if not value:
            raise ValueError("at least one model is required")
        return value

    @field_validator("allowed_origins", "admin_bootstrap_emails", "llm_models", "llm_cheap_models", mode="before")
    @classmethod
    def _parse_str_list(cls, value):
        """Accept a comma-separated string or a JSON array from the env."""
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
