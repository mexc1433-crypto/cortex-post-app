"""Content Providers for Cortex Post."""
from typing import Any

from app.providers.base import BaseProvider
from app.providers.crypto import CryptoProvider
from app.providers.rss import RSSProvider
from app.providers.sports import SportsProvider
from app.providers.weather import WeatherProvider
from app.providers.religious import ReligiousProvider
from app.providers.webhook import WebhookProvider

PROVIDERS: dict[str, type[BaseProvider]] = {
    "crypto": CryptoProvider,
    "rss": RSSProvider,
    "sports": SportsProvider,
    "weather": WeatherProvider,
    "religious": ReligiousProvider,
    "webhook": WebhookProvider,
}


def get_provider(provider_type: str, config: dict[str, Any]) -> BaseProvider | None:
    """Get a provider instance by type and config."""
    provider_class = PROVIDERS.get(provider_type)
    if provider_class:
        return provider_class(config)
    return None


def get_available_provider_types() -> list[str]:
    """Return list of available provider types."""
    return list(PROVIDERS.keys())


__all__ = [
    "BaseProvider",
    "CryptoProvider",
    "RSSProvider",
    "SportsProvider",
    "WeatherProvider",
    "ReligiousProvider",
    "WebhookProvider",
    "get_provider",
    "get_available_provider_types",
]
