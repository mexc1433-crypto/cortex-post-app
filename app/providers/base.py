"""
Base Provider interface for Cortex Post.
All content providers must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Abstract base class for content providers."""
    
    provider_type: str = "base"
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def fetch(self) -> dict[str, Any]:
        """
        Fetch data from the content source.
        
        Returns:
            Dictionary of field names to values.
            Example: {"coin": "BTC", "price": 50000.0, "change_24h": 2.5}
        """
        pass
    
    @abstractmethod
    async def validate_config(self) -> bool:
        """Validate that the provider config is correct and complete."""
        pass
    
    def get_available_fields(self) -> list[str]:
        """Return list of fields this provider can return."""
        return []
