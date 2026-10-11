from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings

# Three deploy tiers. Anything else is rejected at startup so a typo
# (`prod`, `PRODUCTION`, ``) cannot silently flow through the production
# code path. See docs/decisions/0009-environment-tiers-and-config.md for tier semantics.
Environment = Literal["development", "preview", "production"]


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    # Service role key — bypasses RLS; required for server-side storage writes
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # App — comma-separated list of allowed origins, e.g. "http://localhost:3000,http://127.0.0.1:3000"
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    ENVIRONMENT: Environment = "development"

    # Resend email provider
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@roman-technologies.dev"
    RESEND_FROM_NAME: str = "Roman Technologies CMS"
    # Reply-To + "contact us" address on client account emails (welcome,
    # password changed). Replies to noreply@ would otherwise go nowhere.
    SUPPORT_EMAIL: str = "stefanromanpers@gmail.com"

    # Booking
    BOOKING_HOST_EMAIL: str = "stefanromanpers@gmail.com"
    BOOKING_CRON_SECRET: str = ""  # guards POST /booking/cron/reminders

    # Client self-service management (cancel/reschedule)
    BOOKING_PUBLIC_BASE_URL: str = "https://roman-technologies.dev"  # base for /manage/{token}
    # Base URL for building /manage/{token} links (defaults to the public base).
    BOOKING_MANAGE_BASE_URL: str = ""

    # Google Maps lead import (ADR-0012). Empty key disables the feature.
    GOOGLE_MAPS_API_KEY: str = ""
    # Imports per calendar month across all admins. 90 keeps Place Details and
    # Place Photos (10 per import) inside Google's free tier.
    GOOGLE_PLACES_MONTHLY_CAP: int = 90
    GOOGLE_PLACES_MAX_PHOTOS: int = 10

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    @property
    def manage_base_url(self) -> str:
        return self.BOOKING_MANAGE_BASE_URL or self.BOOKING_PUBLIC_BASE_URL

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

    @model_validator(mode="after")
    def _require_service_role_in_prod(self) -> "Settings":
        """Preview and production require the Supabase service-role key.
        Falling back to anon in those tiers means RLS-enabled tables
        silently return zero rows — every admin endpoint breaks with
        an opaque empty response. Fail-loud at startup instead.
        Closes audit finding INFRA-007."""
        if self.ENVIRONMENT in ("preview", "production") and not self.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY must be set when ENVIRONMENT=preview "
                "or ENVIRONMENT=production. Define it in the Vercel dashboard."
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
