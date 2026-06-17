from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, List
import os
import json


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str = ""
    BOT_USERNAME: Optional[str] = ""

    # Web App
    WEBAPP_URL: str = ""
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8000

    # Database
    DATABASE_URL: Optional[str] = None  # لدعم PostgreSQL في Railway
    DATABASE_PATH: str = "cortex_post.db"

    # Admin
    ADMIN_IDS: List[int] = []

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                v = v[1:-1]
            if "," in v:
                return [int(x.strip()) for x in v.split(",") if x.strip()]
            try:
                return [int(v)]
            except ValueError:
                return []
        return []

    # Twitter/X
    TWITTER_API_KEY: Optional[str] = None
    TWITTER_API_SECRET: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_SECRET: Optional[str] = None

    # External APIs
    WEATHER_API_KEY: Optional[str] = None
    SPORTS_API_KEY: Optional[str] = None
    COINGECKO_API_URL: str = "https://api.coingecko.com/api/v3"

    # Freemium Limits
    FREE_MAX_CHANNELS: int = 2
    FREE_MAX_RULES: int = 5
    FREE_MAX_TEMPLATES: int = 3
    PREMIUM_MAX_CHANNELS: int = 999
    PREMIUM_MAX_RULES: int = 999
    PREMIUM_MAX_TEMPLATES: int = 999

    # Scheduler
    SCHEDULER_INTERVAL_SECONDS: int = 60

    # Security
    WEBHOOK_SECRET: Optional[str] = None
    SECRET_KEY: str = os.getenv("SECRET_KEY", "cortex-post-super-secret-change-in-production")

    # Notifications
    ADMIN_NOTIFY_ON_START: bool = True
    ADMIN_NOTIFY_ON_ERROR: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def is_bot_configured(self) -> bool:
        return bool(self.BOT_TOKEN and len(self.BOT_TOKEN) > 15)

    @property
    def use_webhook(self) -> bool:
        return bool(self.WEBAPP_URL and self.WEBAPP_URL.startswith("https"))

    @property
    def database_url(self) -> str:
        """دعم PostgreSQL في Railway + fallback لـ SQLite"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"sqlite+aiosqlite:///{self.DATABASE_PATH}"


settings = Settings()
