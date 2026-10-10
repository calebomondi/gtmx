import os
from supabase import create_client, Client
from supabase.client import ClientOptions

from config import get_settings

cfg = get_settings()

supabase: Client = create_client(
    cfg.supabase_base_url,
    cfg.supabase_secret_key,
    options=ClientOptions(
        postgrest_client_timeout=10,
        storage_client_timeout=10,
        schema="public",
    )
)