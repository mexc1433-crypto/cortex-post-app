"""
Database package for Cortex Post.

Exposes the singleton connection manager, CRUD helpers, and Pydantic models
for convenient imports throughout the application.
"""

from app.database.connection import db
from app.database.crud import init_db
from app.database.models import (
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
    ConditionItem,
    PostLogCreate,
    PostLogResponse,
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
    WebhookEventCreate,
    WebhookEventResponse,
)

__all__ = [
    # Connection
    "db",
    # Initialization
    "init_db",
    # User models
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    # Channel models
    "ChannelCreate",
    "ChannelResponse",
    "ChannelUpdate",
    # Provider models
    "ProviderCreate",
    "ProviderResponse",
    "ProviderUpdate",
    # Template models
    "TemplateCreate",
    "TemplateResponse",
    "TemplateUpdate",
    # Rule models
    "ConditionItem",
    "RuleCreate",
    "RuleResponse",
    "RuleUpdate",
    # Post log models
    "PostLogCreate",
    "PostLogResponse",
    # Webhook event models
    "WebhookEventCreate",
    "WebhookEventResponse",
]
