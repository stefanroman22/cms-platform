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

    # Booking widget — hours below are interpreted in BOOKING_TIMEZONE (CET).
    BOOKING_TIMEZONE: str = "Europe/Berlin"
    # Per-weekday availability windows: "<iso_weekday>=<start_hour>-<end_hour>",
    # comma-separated. Mon=1 .. Sun=7. Days not listed are unavailable.
    BOOKING_HOURS: str = "1=9-20,2=9-20,3=9-20,4=9-20,5=9-20,6=9-17,7=12-17"
    BOOKING_SLOT_MINUTES: int = 45
    BOOKING_BUFFER_MINUTES: int = 0
    BOOKING_MIN_NOTICE_HOURS: int = 2
    BOOKING_HORIZON_DAYS: int = 120
    BOOKING_HOST_EMAIL: str = "stefanromanpers@gmail.com"
    BOOKING_MEETING_URL: str = ""  # standing Meet/Zoom link, shown in emails
    BOOKING_CRON_SECRET: str = ""  # guards POST /booking/cron/reminders

    # Google Calendar auto-sync (over urllib, no extra deps). When these are
    # empty the booking widget falls back to Supabase-only availability — no
    # calendar read/write.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    GOOGLE_CALENDAR_ID: str = "primary"

    # Client self-service management (cancel/reschedule)
    BOOKING_PUBLIC_BASE_URL: str = "https://roman-technologies.dev"  # base for /manage/{token}
    BOOKING_MAX_RESCHEDULES: int = 2
    # Base URL for building /manage/{token} links (defaults to the public base).
    BOOKING_MANAGE_BASE_URL: str = ""

    # Slack — S1 outbound + S1.5 inbound
    SLACK_BOT_TOKEN: str = ""
    SLACK_ISSUES_CHANNEL_ID: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_APPROVER_USER_ID: str = ""
    SLACK_BOT_USER_ID: str = ""
    CMS_DASHBOARD_URL: str = "https://roman-technologies.dev"

    # GitHub PAT for production-promote fast-forward (S1.5)
    GITHUB_TOKEN: str = ""

    # GitHub PAT for triggering Solver Agent workflow via repository_dispatch
    # when a client submits an issue. Scoped narrowly to actions:write on
    # the cms-platform repo (fine-grained PAT). Failures degrade silently —
    # the hourly cron picks up issues whose dispatch did not fire.
    SOLVER_DISPATCH_TOKEN: str = ""
    SOLVER_DISPATCH_REPO: str = "stefanroman22/cms-platform"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    @property
    def booking_hours(self) -> dict[int, tuple[int, int]]:
        """ISO weekday (Mon=1..Sun=7) → (start_hour, end_hour), parsed from
        BOOKING_HOURS. Days absent from the map are unavailable."""
        out: dict[int, tuple[int, int]] = {}
        for part in self.BOOKING_HOURS.split(","):
            part = part.strip()
            if not part:
                continue
            day_s, _, rng = part.partition("=")
            start_s, _, end_s = rng.partition("-")
            out[int(day_s)] = (int(start_s), int(end_s))
        return out

    @property
    def booking_working_days(self) -> set[int]:
        return set(self.booking_hours)

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
