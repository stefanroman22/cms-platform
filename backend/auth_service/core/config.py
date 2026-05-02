from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings


SESSION_COOKIE_NAME: str = "sid"

# Three deploy tiers. Anything else is rejected at startup so a typo
# (`prod`, `PRODUCTION`, ``) cannot silently flow through the production
# code path. See docs/ENVIRONMENTS.md for tier semantics.
Environment = Literal["development", "preview", "production"]


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    # Service role key — bypasses RLS; required for server-side storage writes
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    # Direct PostgreSQL connection string (used by Django / migrations)
    SUPABASE_DB_URL: str = ""

    # App — comma-separated list of allowed origins, e.g. "http://localhost:3000,http://127.0.0.1:3000"
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    ENVIRONMENT: Environment = "development"

    # Resend email provider
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@roman-technologies.dev"
    RESEND_FROM_NAME: str = "Roman Technologies CMS"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _require_origins_in_prod(self) -> "Settings":
        """Production must list its frontend origins. The previous default
        silently fell back to localhost-only, which 403'd every real
        frontend with an opaque CORS error. Fail-loud at startup instead."""
        if self.ENVIRONMENT == "production" and not self.cors_origins:
            raise ValueError(
                "FRONTEND_ORIGINS must be set when ENVIRONMENT=production. "
                "Define it in the Vercel dashboard for cms-backend-roman."
            )
        return self

    model_config = {
        # Single source of truth: backend/.env (sibling of vercel_entry.py).
        # Pass B of the env-hygiene plan moved it up from auth_service/.
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
