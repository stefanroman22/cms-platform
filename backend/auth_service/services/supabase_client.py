"""The backend's Supabase client, with an explicit privilege level in its name.

`get_supabase_admin()` uses the service-role / secret key and bypasses RLS.
Every router uses it; authorization is enforced in application code.

Before audit finding INFRA-003, `get_supabase()` was the only entry point and
silently used the service-role key, so the name hid the privilege level. The
explicit `_admin` name is the fix. An anon-key client (`get_supabase_anon()`)
was added alongside it for future RLS defense-in-depth, but nothing ever
called it, so it and `SUPABASE_ANON_KEY` were removed. If a path ever needs
RLS enforcement, add an anon client back next to this one and name it the
same way.
"""

from supabase import Client, create_client

from ..core.config import settings

_admin_client: Client | None = None


def get_supabase_admin() -> Client:
    """Service-role client. Bypasses RLS. Authorization is enforced in
    application code — every caller must already have validated that the
    requesting user is permitted to perform the operation."""
    global _admin_client
    if _admin_client is None:
        # Preview and production can't start without the service-role key
        # (model_validator in `core/config.py`); in development, fail here.
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        if not key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for the admin client")
        _admin_client = create_client(settings.SUPABASE_URL, key)
    return _admin_client
