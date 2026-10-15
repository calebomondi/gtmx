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
from typing import Annotated, Literal

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
    project_name: str = "Thalace"
    api_v1_str: str = "/api/v1"
    environment: str = "development"
    log_level: str = Field("INFO", validation_alias="GTMX_LOG_LEVEL")
    # "text" for a terminal, "json" (one object per line) for a log shipper.
    log_format: Literal["text", "json"] = Field("text", validation_alias="GTMX_LOG_FORMAT")
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
    # Connections the app holds: SQLAlchemy's pool (size + overflow) plus the
    # agent checkpointer's fixed pool. Their sum must fit the database's limit
    # (Supabase's session pooler allows few on small plans).
    db_pool_size: int = 5
    db_max_overflow: int = 10
    checkpointer_pool_size: int = 10

    # -- LLM providers --
    dashscope_api_key: str = ""
    dashscope_base_url: str = ""
    openai_api_key: str = ""
    # Qwen models, tried in order (comma-separated in env). `llm_models` serves
    # reasoning calls; `llm_cheap_models` the bulk extraction/condensing calls.
    # qwen3.7-plus: the account's free quota on the 3.8 family (max, flash,
    # omni-flash) is exhausted (2026-10-10). Override via env.
    llm_models: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["qwen-plus-2025-04-28", "qwen-plus-2025-07-14", "qwen-plus-latest", "qwen-max", ""])
    llm_cheap_models: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["qwen-plus-2025-04-28", "qwen-plus-2025-07-14", "qwen-plus-latest", "qwen-max", ""])
    # Second provider (OpenRouter, keyed by OPENAI_API_KEY), tried in order when
    # every Qwen model fails -- outage, quota, or a model retired mid-run.
    llm_fallback_models: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["openai/gpt-4o-mini"])
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Per-call cap. Comfortably above the slowest call measured (~150s for a
    # ~8k-token structured output), far below the old 600s that let one hung
    # connection stall a run for ten minutes.
    llm_call_timeout_s: float = 240.0
    # Max LLM calls in flight per provider (process-wide); past it calls queue.
    llm_max_concurrency: int = 24

    # -- Web data --
    # Hard cap per Exa call; its SDK sets no timeout of its own.
    exa_timeout_s: float = 60.0
    exa_api_key: str = ""
    brightdata_api_key: str = ""
    composio_api_key: str = ""
    # Composio auth config per toolkit, for toolkits Composio does not manage
    # auth for (verified 2026-10-10: tiktok, twitter). JSON object, e.g.
    # COMPOSIO_AUTH_CONFIGS={"twitter": "ac_...", "tiktok": "ac_..."}
    composio_auth_configs: dict[str, str] = Field(default_factory=dict)
    # Where users land after connecting an account (the SPA's origin).
    frontend_base_url: str = "http://localhost:5173"

    # -- Runs --
    # Threads for the event loop's default executor (sync graph nodes and
    # asyncio.to_thread). Each running discovery holds up to two for minutes.
    default_executor_workers: int = 256
    # Wall-clock cap on one active segment of a run (time spent waiting for a
    # user's answer does not count: no task is alive then).
    discovery_segment_timeout_s: float = 1800.0
    # Wall-clock cap on a whole background run (competitors, accounts, ...).
    background_run_timeout_s: float = 1800.0

    # -- Usage limits (per user) --
    max_active_discovery_runs: int = 1
    max_discovery_runs_per_day: int = 10
    max_competitor_runs_per_day: int = 20
    max_account_runs_per_day: int = 20
    max_requests_per_minute: int = 120
    max_chat_messages_per_day: int = 200
    max_outreach_sends_per_day: int = 50
    max_monitor_runs_per_day: int = 6

    # -- Activity tracking (customer app heartbeats) --
    # The app pings this often while the user is active; a ping credits the
    # time since the previous one, capped so a sleeping laptop isn't counted.
    activity_heartbeat_s: int = 60
    activity_max_credit_s: int = 120
    # Longer than this without a ping and the next one starts a new session.
    activity_session_gap_s: int = 300

    # -- Inbox sync (replies to sent outreach, from the user's Gmail) --
    inbox_sync_enabled: bool = True
    # How often every user with recent sends is checked for replies/bounces.
    inbox_sync_interval_s: float = 300.0
    # Only threads sent within this window are watched for replies.
    inbox_sync_window_days: int = 30

    # -- Waitlist (public landing page at thalace.com) --
    # Resend sends the signup confirmation. It only delivers to any address
    # once the sending domain is verified in Resend; until `waitlist_from_email`
    # is set (e.g. "Thalace <hello@thalace.com>"), signups are saved and no email goes.
    resend_api_key: str = ""
    resend_timeout_s: float = 15.0
    waitlist_from_email: str = ""
    waitlist_pilot_spots: int = 50
    # Days after signup the team reaches out to pilot opt-ins (said in the email).
    waitlist_pilot_contact_days: int = 14
    waitlist_signups_per_ip_per_hour: int = 5
    # Salt for the stored IP hash (rate limiting without keeping raw IPs).
    waitlist_ip_salt: str = "gtmx-waitlist"
    # The header the proxy in front of the backend puts the visitor's IP in:
    # x-real-ip behind our nginx, x-forwarded-for on Render (first entry).
    client_ip_header: str = "x-real-ip"

    # -- Observability (all opt-in: empty means off) --
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1
    langsmith_api_key: str = ""
    langsmith_project: str = "gtmx"

    # -- Cost reporting (admin dashboard) --
    # List prices in USD, used only to estimate spend; confirm against each
    # provider's current price sheet. LLM: [input, output] per 1M tokens, keyed
    # by model id; a model missing here is reported as unpriced, never as $0.
    llm_prices: dict[str, list[float]] = Field(default_factory=lambda: {
        "qwen3.7-plus": [0.4, 1.2],
        "openai/gpt-4o-mini": [0.15, 0.6],
    })
    # Per call, keyed "provider.operation", or "provider" as a fallback.
    api_call_prices: dict[str, float] = Field(default_factory=lambda: {
        "exa.search": 0.01,  # search + text for ~5 results
        "exa.contents": 0.001,
        "brightdata": 0.0015,  # per scraped record
    })

    # -- Competitor monitoring --
    # How often the scheduler looks for stale workspaces, and how old a check
    # may get before it is redone.
    monitor_enabled: bool = True
    monitor_scan_interval_s: float = 3600.0
    # Grace period after boot before the first sweep, so a restart (or a local
    # dev reload) doesn't immediately fan out paid monitoring runs.
    monitor_initial_delay_s: float = 120.0
    monitor_max_age_h: float = 24.0
    # Social stats move slowly and every Bright Data scrape is paid, so a
    # monitor run refreshes them only when they are older than this.
    socials_max_age_h: float = 168.0

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

    @field_validator("allowed_origins", "admin_bootstrap_emails", "llm_models", "llm_cheap_models", "llm_fallback_models", mode="before")
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
