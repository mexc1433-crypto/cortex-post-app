from pydantic_settings import BaseSettings
from typing import Optional
import os


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

    # Admin
    ADMIN_IDS: list[int] = []

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
