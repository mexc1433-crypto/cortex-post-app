from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str
    BOT_USERNAME: Optional[str] = ""

    # Web App
    WEBAPP_URL: str = "https://cortex-post.up.railway.app"
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8000

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


settings = Settings()
