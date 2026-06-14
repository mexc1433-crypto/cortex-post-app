"""Freemium system - enforces tier limits."""
import logging

from app.config import settings
from app.database import crud

logger = logging.getLogger(__name__)


class FreemiumLimits:
    """Enforces freemium tier limits."""
    
    @staticmethod
    async def can_add_channel(user_id: int) -> bool:
        """Check if user can add another channel."""
        user = await crud.get_user_by_id(user_id)
        if not user:
            return False
        
        if user["tier"] == "premium":
            return True
        
        channels = await crud.get_channels_by_user(user_id)
        return len(channels) < settings.FREE_MAX_CHANNELS
    
    @staticmethod
    async def can_add_rule(user_id: int) -> bool:
        """Check if user can add another rule."""
        user = await crud.get_user_by_id(user_id)
        if not user:
            return False
        
        if user["tier"] == "premium":
            return True
        
        rules = await crud.get_rules_by_user(user_id)
        return len(rules) < settings.FREE_MAX_RULES
    
    @staticmethod
    async def can_add_template(user_id: int) -> bool:
        """Check if user can add another template."""
        user = await crud.get_user_by_id(user_id)
        if not user:
            return False
        
        if user["tier"] == "premium":
            return True
        
        templates = await crud.get_templates_by_user(user_id)
        return len(templates) < settings.FREE_MAX_TEMPLATES
    
    @staticmethod
    async def can_use_twitter(user_id: int) -> bool:
        """Check if user can use Twitter publishing (premium only)."""
        user = await crud.get_user_by_id(user_id)
        return user is not None and user["tier"] == "premium"
    
    @staticmethod
    async def can_use_webhook(user_id: int) -> bool:
        """Check if user can use Webhook provider (premium only)."""
        user = await crud.get_user_by_id(user_id)
        return user is not None and user["tier"] == "premium"
    
    @staticmethod
    async def get_user_limits(user_id: int) -> dict:
        """Get current usage and limits for a user."""
        user = await crud.get_user_by_id(user_id)
        if not user:
            return {}
        
        tier = user["tier"]
        channels = await crud.get_channels_by_user(user_id)
        rules = await crud.get_rules_by_user(user_id)
        templates = await crud.get_templates_by_user(user_id)
        
        max_channels = settings.PREMIUM_MAX_CHANNELS if tier == "premium" else settings.FREE_MAX_CHANNELS
        max_rules = settings.PREMIUM_MAX_RULES if tier == "premium" else settings.FREE_MAX_RULES
        max_templates = settings.PREMIUM_MAX_TEMPLATES if tier == "premium" else settings.FREE_MAX_TEMPLATES
        
        return {
            "tier": tier,
            "channels": {"used": len(channels), "max": max_channels},
            "rules": {"used": len(rules), "max": max_rules},
            "templates": {"used": len(templates), "max": max_templates},
            "twitter_available": tier == "premium",
            "webhook_available": tier == "premium",
        }


freemium = FreemiumLimits()
