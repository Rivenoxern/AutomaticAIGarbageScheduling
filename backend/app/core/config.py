"""
app/core/config.py
──────────────────
Centralised settings loaded from the .env file via pydantic-settings.
All other modules import from here instead of reading os.environ directly.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/wasteway_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change_me"


settings = Settings()
