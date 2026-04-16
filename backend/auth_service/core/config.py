from pydantic_settings import BaseSettings
from pathlib import Path

# auth_service/core/config.py → parent = core → parent = auth_service → parent = backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # = backend/


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    # Service role key — bypasses RLS; required for server-side storage writes
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    # Direct PostgreSQL connection string (used by Django / migrations)
    SUPABASE_DB_URL: str = ""

    # JWT (RS256)
    PRIVATE_KEY_PATH: str = str(BASE_DIR / "keys" / "private.pem")
    PUBLIC_KEY_PATH: str = str(BASE_DIR / "keys" / "public.pem")
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER_ME: int = 60

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

    @property
    def private_key(self) -> str:
        return Path(self.PRIVATE_KEY_PATH).read_text()

    @property
    def public_key(self) -> str:
        return Path(self.PUBLIC_KEY_PATH).read_text()

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
