from pydantic_settings import BaseSettings
from pathlib import Path


SESSION_COOKIE_NAME: str = "sid"


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
    ENVIRONMENT: str = "development"

    # Resend email provider
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@romantechnologies.com"
    RESEND_FROM_NAME: str = "Roman Technologies CMS"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    model_config = {
        # Single source of truth: backend/.env (sibling of vercel_entry.py).
        # Pass B of the env-hygiene plan moved it up from auth_service/.
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
