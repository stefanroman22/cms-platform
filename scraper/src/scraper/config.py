"""pydantic-settings — single Settings class read from .env, matching
the CMS backend's convention (settings = Settings())."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    GOOGLE_SHEETS_CREDENTIALS_JSON: str = ""
    GOOGLE_SHEET_ID: str = ""

    SCRAPER_HEADLESS: bool = True
    SCRAPER_LOCALE_DEFAULT: str = "en"
    SCRAPER_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    SCRAPER_MIN_DELAY_MS: int = 600
    SCRAPER_MAX_DELAY_MS: int = 2200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
