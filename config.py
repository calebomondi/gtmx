from os import environ
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:

    dashscope_api_key: str = field(default_factory=lambda: environ.get("DASHSCOPE_API_KEY", ""))
    dashscope_base_url: str = field(default_factory=lambda: environ.get("DASHSCOPE_BASE_URL", ""))
    dashscope_embed_model: str = field(default_factory=lambda: environ.get("DASHSCOPE_EMBED_MODEL", "text-embedding-v4"))

    exa_api_key: str = field(default_factory=lambda: environ.get("EXA_API_KEY", ""))
    tavily_api_key: str = field(default_factory=lambda: environ.get("TAVILY_API_KEY", ""))

    # How far back (in days) market research may look for sources. Kept short so
    # the market interview is grounded in CURRENT conditions, not history.
    market_recency_days: int = field(default_factory=lambda: int(environ.get("MARKET_RECENCY_DAYS", "365")))

    openai_api_key: str = field(default_factory=lambda: environ.get("OPENAI_API_KEY", ""))

    supabase_base_url: str = field(default_factory=lambda: environ.get("SUPABASE_BASE_URL", ""))
    supabase_anon_key: str = field(default_factory=lambda: environ.get("SUPABASE_ANON_KEY", ""))
    supabase_secret_key: str = field(default_factory=lambda: environ.get("SUPABASE_SECRET_KEY", ""))
    supabase_db_conn_str: str = field(default_factory=lambda: environ.get("SUPABASE_DB_CONN_STR", ""))

    @classmethod
    def from_env(cls) -> "Config":
        return cls()
