"""Webhook provider - receives incoming data via HTTP POST."""
import logging
from typing import Any

from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class WebhookProvider(BaseProvider):
    provider_type = "webhook"
    
    async def fetch(self) -> dict[str, Any]:
        """Webhooks don't fetch - they receive data via the API endpoint."""
        return {}
    
    async def validate_config(self) -> bool:
        return True
    
    def get_available_fields(self) -> list[str]:
        return ["*"]  # Webhook data is dynamic, any field is possible
