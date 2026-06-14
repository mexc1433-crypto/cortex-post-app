"""Base Publisher interface for Cortex Post."""
from abc import ABC, abstractmethod


class BasePublisher(ABC):
    """Abstract base class for platform publishers."""
    
    platform: str = "base"
    
    @abstractmethod
    async def publish(self, **kwargs) -> int | str | None:
        """
        Publish content to the platform.
        
        Returns:
            Message/tweet ID on success, None on failure
        """
        pass
    
    @abstractmethod
    async def delete(self, message_id: int | str, **kwargs) -> bool:
        """Delete a published message/tweet."""
        pass
