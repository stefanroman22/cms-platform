"""Two distinct Supabase clients with explicit privilege levels.

Why two:
- `get_supabase_anon()`  uses the publishable / anon key. Subject to RLS.
  Used for paths where a future RLS policy could add defense-in-depth even
  if the application-layer authorization has a bug. (Not currently a heavily-
  used path because most tables don't have RLS policies yet — see audit
  finding BE-010 — but the boundary now exists.)
- `get_supabase_admin()` uses the service-role / secret key. Bypasses RLS.
  Used for everything that needs to read/write across users — every router
  in this codebase today.

Before this split (audit finding INFRA-003), `get_supabase()` was the only
entry point and silently used the service-role key, collapsing the privilege
boundary the naming implied. Every existing call site was migrated to the
explicit `get_supabase_admin()` name in the same change so behaviour is
unchanged; new code makes an explicit choice.
"""

from supabase import Client, create_client

from ..core.config import settings

_anon_client: Client | None = None
_admin_client: Client | None = None


def get_supabase_anon() -> Client:
    """Anon-key client. Subject to RLS; will fail closed against any table
    that has RLS enabled with no permissive policy for `anon`."""
    global _anon_client
    if _anon_client is None:
        if not settings.SUPABASE_ANON_KEY:
            raise RuntimeError("SUPABASE_ANON_KEY is required for the anon Supabase client")
        _anon_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _anon_client


def get_supabase_admin() -> Client:
    """Service-role client. Bypasses RLS. Authorization is enforced in
    application code — every caller must already have validated that the
    requesting user is permitted to perform the operation."""
    global _admin_client
    if _admin_client is None:
        # Fail loud in non-dev: prod must always have the service-role key
        # set (model_validator in `core/config.py` enforces this).
        key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
        if not key:
            raise RuntimeError(
                "SUPABASE_SERVICE_ROLE_KEY (or anon fallback) required for admin client"
            )
        _admin_client = create_client(settings.SUPABASE_URL, key)
    return _admin_client
