from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import field_validator
import os
import json


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str = ""  # Optional - app will start but bot won't work without it
    BOT_USERNAME: Optional[str] = ""

    # Web App - Railway provides PORT env variable
    WEBAPP_URL: str = ""
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = int(os.environ.get("PORT", "8000"))  # Railway provides PORT

    # Database
    DATABASE_PATH: str = "cortex_post.db"

    # Admin - accepts: "7005859703" or "[7005859703]" or "7005859703,123456"
    ADMIN_IDS: list[int] = []

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        """Parse ADMIN_IDS from various string formats."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # Handle "[7005859703]" format
            if v.startswith("[") and v.endswith("]"):
                v = v[1:-1]
            # Handle comma-separated
            if "," in v:
                return [int(x.strip()) for x in v.split(",") if x.strip()]
            # Single number
            try:
                return [int(v)]
            except ValueError:
                return []
        return []

    # Twitter/X
    TWITTER_API_KEY: Optional[str] = ""
    TWITTER_API_SECRET: Optional[str] = ""
    TWITTER_ACCESS_TOKEN: Optional[str] = ""
    TWITTER_ACCESS_SECRET: Optional[str] = ""

    # Weather API
    WEATHER_API_KEY: Optional[str] = ""

    # Crypto APIs
    COINGECKO_API_URL: str = "https://api.coingecko.com/api/v3"

    # Sports API
    SPORTS_API_KEY: Optional[str] = ""
    SPORTS_API_URL: str = "https://api.football-data.org/v4"

    # Freemium
    FREE_MAX_CHANNELS: int = 2
    FREE_MAX_RULES: int = 5
    FREE_MAX_TEMPLATES: int = 3
    PREMIUM_MAX_CHANNELS: int = 999
    PREMIUM_MAX_RULES: int = 999
    PREMIUM_MAX_TEMPLATES: int = 999

    # Scheduler
    SCHEDULER_INTERVAL_SECONDS: int = 60

    # Webhook secret for providers
    WEBHOOK_SECRET: Optional[str] = ""

    # Admin notifications
    ADMIN_NOTIFY_ON_START: bool = True  # Send admin notification when bot starts
    ADMIN_NOTIFY_ON_ERROR: bool = True  # Send admin notification on errors

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def is_bot_configured(self) -> bool:
        """Check if bot token is configured."""
        return bool(self.BOT_TOKEN and len(self.BOT_TOKEN) > 10)

    @property
    def use_webhook(self) -> bool:
        """Determine if webhook mode should be used."""
        return bool(self.WEBAPP_URL and self.WEBAPP_URL.startswith("https://"))


settings = Settings()
