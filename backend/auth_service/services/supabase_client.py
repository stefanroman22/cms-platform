from supabase import Client, create_client

from ..core.config import settings

_client: Client | None = None
_admin_client: Client | None = None


def get_supabase() -> Client:
    """Server-side Supabase client. Uses the service role key to bypass RLS —
    this is a backend-only service, authorization is enforced in application code."""
    global _client
    if _client is None:
        key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
        _client = create_client(settings.SUPABASE_URL, key)
    return _client


def get_supabase_admin() -> Client:
    """Uses the service role key to bypass RLS.
    Falls back to the anon key when SUPABASE_SERVICE_ROLE_KEY is not set (dev only)."""
    global _admin_client
    if _admin_client is None:
        key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
        _admin_client = create_client(settings.SUPABASE_URL, key)
    return _admin_client
