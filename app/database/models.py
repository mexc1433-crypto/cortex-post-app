"""
Pydantic models for all database tables.

These models serve as request/response schemas and validation layers
between the database and the application logic.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# User models
# ============================================================================


class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "ar"


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str
    tier: str
    premium_expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    tier: Optional[str] = None
    premium_expires_at: Optional[datetime] = None


# ============================================================================
# Channel models
# ============================================================================


class ChannelCreate(BaseModel):
    channel_telegram_id: int
    channel_title: str
    channel_username: Optional[str] = None
    channel_type: str = "channel"


class ChannelResponse(BaseModel):
    id: int
    user_id: int
    channel_telegram_id: int
    channel_title: str
    channel_username: Optional[str] = None
    channel_type: str
    is_active: bool
    created_at: Optional[datetime] = None


class ChannelUpdate(BaseModel):
    channel_title: Optional[str] = None
    channel_username: Optional[str] = None
    channel_type: Optional[str] = None
    is_active: Optional[bool] = None


# ============================================================================
# Provider models
# ============================================================================


class ProviderCreate(BaseModel):
    provider_type: str  # crypto, rss, sports, weather, religious, webhook
    name: str
    config: dict  # JSON config specific to provider type
    is_active: bool = True


class ProviderResponse(BaseModel):
    id: int
    user_id: int
    provider_type: str
    name: str
    config: dict
    is_active: bool
    last_fetched_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None


# ============================================================================
# Template models
# ============================================================================


class TemplateCreate(BaseModel):
    name: str
    content: str
    provider_type: str
    parse_mode: str = "HTML"


class TemplateResponse(BaseModel):
    id: int
    user_id: int
    name: str
    content: str
    provider_type: str
    parse_mode: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    parse_mode: Optional[str] = None


# ============================================================================
# Rule models
# ============================================================================


class ConditionItem(BaseModel):
    field: str
    operator: str  # >, <, >=, <=, ==, !=, contains, not_contains, starts_with, between
    value: Any


class RuleCreate(BaseModel):
    name: str
    provider_id: int
    template_id: int
    channel_id: int
    conditions: list[ConditionItem]
    condition_logic: str = "AND"
    is_active: bool = True
    cooldown_minutes: int = 30
    priority: int = 0


class RuleResponse(BaseModel):
    id: int
    user_id: int
    name: str
    provider_id: int
    template_id: int
    channel_id: int
    conditions: list[dict]
    condition_logic: str
    is_active: bool
    cooldown_minutes: int
    last_triggered_at: Optional[datetime] = None
    priority: int
    created_at: Optional[datetime] = None


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[list[ConditionItem]] = None
    condition_logic: Optional[str] = None
    is_active: Optional[bool] = None
    cooldown_minutes: Optional[int] = None
    template_id: Optional[int] = None
    channel_id: Optional[int] = None
    priority: Optional[int] = None


# ============================================================================
# Post log models
# ============================================================================


class PostLogCreate(BaseModel):
    rule_id: int
    channel_id: int
    provider_type: str
    content: str
    status: str = "sent"
    platform: str = "telegram"
    telegram_message_id: Optional[int] = None
    error_message: Optional[str] = None


class PostLogResponse(BaseModel):
    id: int
    rule_id: int
    channel_id: int
    provider_type: str
    content: str
    status: str
    platform: str
    telegram_message_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


# ============================================================================
# Webhook event models
# ============================================================================


class WebhookEventCreate(BaseModel):
    provider_id: Optional[int] = None
    payload: dict
    source_ip: Optional[str] = None


class WebhookEventResponse(BaseModel):
    id: int
    provider_id: Optional[int] = None
    payload: dict
    source_ip: Optional[str] = None
    processed: bool
    created_at: Optional[datetime] = None
