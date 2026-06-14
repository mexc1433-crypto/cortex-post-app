"""
CRUD operations for all database tables.

Every function is async and uses the shared ``db`` singleton from
``app.database.connection``.  Row results are converted to plain dicts
before being returned so that callers never depend on aiosqlite internals.

JSON columns (config, conditions, payload) are automatically serialized
on write and deserialized on read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.database.connection import db
from app.database.models import (
    ChannelCreate,
    ChannelUpdate,
    ProviderCreate,
    ProviderUpdate,
    RuleCreate,
    RuleUpdate,
    TemplateCreate,
    TemplateUpdate,
    UserCreate,
    UserUpdate,
    WebhookEventCreate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _json_dumps(value: Any) -> str:
    """Serialize a Python object to a JSON string."""
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: Optional[str]) -> Any:
    """Deserialize a JSON string, returning None for empty input."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        # Already deserialized (e.g. by aiosqlite Row)
        return value
    return json.loads(value)


def _deserialize_row(row: Optional[dict[str, Any]], json_fields: tuple[str, ...]) -> Optional[dict[str, Any]]:
    """Deserialize JSON fields in a row dict."""
    if row is None:
        return None
    for field in json_fields:
        if field in row and row[field] is not None:
            row[field] = _json_loads(row[field])
    return row


def _deserialize_rows(rows: list[dict[str, Any]], json_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """Deserialize JSON fields across many row dicts."""
    return [_deserialize_row(r, json_fields) for r in rows]


# ===========================================================================
# Database initialization
# ===========================================================================


async def init_db() -> None:
    """Create all tables and indexes defined in schema.sql."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    await db.execute_script(schema_sql)


# ===========================================================================
# Users
# ===========================================================================


async def create_user(data: UserCreate) -> dict[str, Any]:
    """Insert a new user and return the created row."""
    cursor = await db.execute(
        """
        INSERT INTO users (telegram_id, username, first_name, last_name, language_code)
        VALUES (?, ?, ?, ?, ?)
        """,
        (data.telegram_id, data.username, data.first_name, data.last_name, data.language_code),
    )
    user_id = cursor.lastrowid
    row = await db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    return row  # type: ignore[return-value]


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict[str, Any]]:
    """Look up a user by their Telegram ID."""
    return await db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))


async def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    """Look up a user by primary key."""
    return await db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))


async def update_user(user_id: int, data: UserUpdate) -> Optional[dict[str, Any]]:
    """Update a user's fields. Only non-None fields in ``data`` are applied."""
    fields: list[str] = []
    values: list[Any] = []
    for field_name, value in data.model_dump(exclude_unset=True).items():
        fields.append(f"{field_name} = ?")
        values.append(value)

    if not fields:
        return await get_user_by_id(user_id)

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(user_id)

    await db.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
        tuple(values),
    )
    return await get_user_by_id(user_id)


async def get_or_create_user(data: UserCreate) -> dict[str, Any]:
    """Return an existing user by telegram_id, or create one if missing."""
    existing = await get_user_by_telegram_id(data.telegram_id)
    if existing is not None:
        return existing
    return await create_user(data)


# ===========================================================================
# Channels
# ===========================================================================


async def create_channel(user_id: int, data: ChannelCreate) -> dict[str, Any]:
    """Insert a new channel for a user and return the created row."""
    cursor = await db.execute(
        """
        INSERT INTO channels (user_id, channel_telegram_id, channel_title, channel_username, channel_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, data.channel_telegram_id, data.channel_title, data.channel_username, data.channel_type),
    )
    channel_id = cursor.lastrowid
    row = await db.fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))
    return row  # type: ignore[return-value]


async def get_channels_by_user(user_id: int) -> list[dict[str, Any]]:
    """Return all channels belonging to a user."""
    return await db.fetchall("SELECT * FROM channels WHERE user_id = ?", (user_id,))


async def get_channel_by_id(channel_id: int) -> Optional[dict[str, Any]]:
    """Return a single channel by primary key."""
    return await db.fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))


async def update_channel(channel_id: int, data: ChannelUpdate) -> Optional[dict[str, Any]]:
    """Update a channel's fields."""
    fields: list[str] = []
    values: list[Any] = []
    for field_name, value in data.model_dump(exclude_unset=True).items():
        fields.append(f"{field_name} = ?")
        values.append(value)

    if not fields:
        return await get_channel_by_id(channel_id)

    values.append(channel_id)
    await db.execute(
        f"UPDATE channels SET {', '.join(fields)} WHERE id = ?",
        tuple(values),
    )
    return await get_channel_by_id(channel_id)


async def delete_channel(channel_id: int) -> bool:
    """Delete a channel by primary key. Returns True if a row was deleted."""
    cursor = await db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    return cursor.rowcount > 0


# ===========================================================================
# Providers
# ===========================================================================

_PROVIDER_JSON_FIELDS = ("config",)


async def create_provider(user_id: int, data: ProviderCreate) -> dict[str, Any]:
    """Insert a new content provider for a user."""
    cursor = await db.execute(
        """
        INSERT INTO providers (user_id, provider_type, name, config, is_active)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, data.provider_type, data.name, _json_dumps(data.config), int(data.is_active)),
    )
    provider_id = cursor.lastrowid
    row = await db.fetchone("SELECT * FROM providers WHERE id = ?", (provider_id,))
    return _deserialize_row(row, _PROVIDER_JSON_FIELDS)  # type: ignore[return-value]


async def get_providers_by_user(user_id: int) -> list[dict[str, Any]]:
    """Return all providers belonging to a user."""
    rows = await db.fetchall("SELECT * FROM providers WHERE user_id = ?", (user_id,))
    return _deserialize_rows(rows, _PROVIDER_JSON_FIELDS)


async def get_provider_by_id(provider_id: int) -> Optional[dict[str, Any]]:
    """Return a single provider by primary key."""
    row = await db.fetchone("SELECT * FROM providers WHERE id = ?", (provider_id,))
    return _deserialize_row(row, _PROVIDER_JSON_FIELDS)


async def get_providers_by_type(provider_type: str) -> list[dict[str, Any]]:
    """Return all active providers of a given type."""
    rows = await db.fetchall(
        "SELECT * FROM providers WHERE provider_type = ? AND is_active = 1",
        (provider_type,),
    )
    return _deserialize_rows(rows, _PROVIDER_JSON_FIELDS)


async def update_provider(provider_id: int, data: ProviderUpdate) -> Optional[dict[str, Any]]:
    """Update a provider's fields."""
    fields: list[str] = []
    values: list[Any] = []
    dump = data.model_dump(exclude_unset=True)

    if "name" in dump:
        fields.append("name = ?")
        values.append(dump["name"])
    if "config" in dump:
        fields.append("config = ?")
        values.append(_json_dumps(dump["config"]))
    if "is_active" in dump:
        fields.append("is_active = ?")
        values.append(int(dump["is_active"]))

    if not fields:
        return await get_provider_by_id(provider_id)

    values.append(provider_id)
    await db.execute(
        f"UPDATE providers SET {', '.join(fields)} WHERE id = ?",
        tuple(values),
    )
    return await get_provider_by_id(provider_id)


async def delete_provider(provider_id: int) -> bool:
    """Delete a provider by primary key. Returns True if a row was deleted."""
    cursor = await db.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
    return cursor.rowcount > 0


async def update_last_fetched(provider_id: int) -> None:
    """Set last_fetched_at to the current timestamp."""
    await db.execute(
        "UPDATE providers SET last_fetched_at = CURRENT_TIMESTAMP WHERE id = ?",
        (provider_id,),
    )


# ===========================================================================
# Templates
# ===========================================================================


async def create_template(user_id: int, data: TemplateCreate) -> dict[str, Any]:
    """Insert a new template for a user."""
    cursor = await db.execute(
        """
        INSERT INTO templates (user_id, name, content, provider_type, parse_mode)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, data.name, data.content, data.provider_type, data.parse_mode),
    )
    template_id = cursor.lastrowid
    row = await db.fetchone("SELECT * FROM templates WHERE id = ?", (template_id,))
    return row  # type: ignore[return-value]


async def get_templates_by_user(user_id: int) -> list[dict[str, Any]]:
    """Return all templates belonging to a user."""
    return await db.fetchall("SELECT * FROM templates WHERE user_id = ?", (user_id,))


async def get_template_by_id(template_id: int) -> Optional[dict[str, Any]]:
    """Return a single template by primary key."""
    return await db.fetchone("SELECT * FROM templates WHERE id = ?", (template_id,))


async def get_templates_by_provider_type(provider_type: str) -> list[dict[str, Any]]:
    """Return all templates for a given provider type."""
    return await db.fetchall(
        "SELECT * FROM templates WHERE provider_type = ?",
        (provider_type,),
    )


async def update_template(template_id: int, data: TemplateUpdate) -> Optional[dict[str, Any]]:
    """Update a template's fields."""
    fields: list[str] = []
    values: list[Any] = []
    for field_name, value in data.model_dump(exclude_unset=True).items():
        fields.append(f"{field_name} = ?")
        values.append(value)

    if not fields:
        return await get_template_by_id(template_id)

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(template_id)

    await db.execute(
        f"UPDATE templates SET {', '.join(fields)} WHERE id = ?",
        tuple(values),
    )
    return await get_template_by_id(template_id)


async def delete_template(template_id: int) -> bool:
    """Delete a template by primary key. Returns True if a row was deleted."""
    cursor = await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    return cursor.rowcount > 0


# ===========================================================================
# Rules
# ===========================================================================

_RULE_JSON_FIELDS = ("conditions",)


async def create_rule(user_id: int, data: RuleCreate) -> dict[str, Any]:
    """Insert a new rule for a user."""
    conditions_json = _json_dumps([c.model_dump() for c in data.conditions])
    cursor = await db.execute(
        """
        INSERT INTO rules (user_id, name, provider_id, template_id, channel_id,
                           conditions, condition_logic, is_active, cooldown_minutes, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            data.name,
            data.provider_id,
            data.template_id,
            data.channel_id,
            conditions_json,
            data.condition_logic,
            int(data.is_active),
            data.cooldown_minutes,
            data.priority,
        ),
    )
    rule_id = cursor.lastrowid
    row = await db.fetchone("SELECT * FROM rules WHERE id = ?", (rule_id,))
    return _deserialize_row(row, _RULE_JSON_FIELDS)  # type: ignore[return-value]


async def get_rules_by_user(user_id: int) -> list[dict[str, Any]]:
    """Return all rules belonging to a user."""
    rows = await db.fetchall("SELECT * FROM rules WHERE user_id = ?", (user_id,))
    return _deserialize_rows(rows, _RULE_JSON_FIELDS)


async def get_active_rules() -> list[dict[str, Any]]:
    """Return all active rules across all users (used by the scheduler)."""
    rows = await db.fetchall("SELECT * FROM rules WHERE is_active = 1 ORDER BY priority DESC")
    return _deserialize_rows(rows, _RULE_JSON_FIELDS)


async def get_rule_by_id(rule_id: int) -> Optional[dict[str, Any]]:
    """Return a single rule by primary key."""
    row = await db.fetchone("SELECT * FROM rules WHERE id = ?", (rule_id,))
    return _deserialize_row(row, _RULE_JSON_FIELDS)


async def update_rule(rule_id: int, data: RuleUpdate) -> Optional[dict[str, Any]]:
    """Update a rule's fields."""
    fields: list[str] = []
    values: list[Any] = []
    dump = data.model_dump(exclude_unset=True)

    # Handle JSON conditions separately
    if "conditions" in dump and dump["conditions"] is not None:
        fields.append("conditions = ?")
        values.append(_json_dumps(dump["conditions"]))
        del dump["conditions"]

    for field_name, value in dump.items():
        if field_name == "is_active" and value is not None:
            fields.append("is_active = ?")
            values.append(int(value))
        else:
            fields.append(f"{field_name} = ?")
            values.append(value)

    if not fields:
        return await get_rule_by_id(rule_id)

    values.append(rule_id)
    await db.execute(
        f"UPDATE rules SET {', '.join(fields)} WHERE id = ?",
        tuple(values),
    )
    return await get_rule_by_id(rule_id)


async def delete_rule(rule_id: int) -> bool:
    """Delete a rule by primary key. Returns True if a row was deleted."""
    cursor = await db.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    return cursor.rowcount > 0


async def update_last_triggered(rule_id: int) -> None:
    """Set last_triggered_at to the current timestamp."""
    await db.execute(
        "UPDATE rules SET last_triggered_at = CURRENT_TIMESTAMP WHERE id = ?",
        (rule_id,),
    )


# ===========================================================================
# Post Log
# ===========================================================================


async def create_post_log(
    rule_id: int,
    channel_id: int,
    provider_type: str,
    content: str,
    status: str = "sent",
    platform: str = "telegram",
    telegram_message_id: Optional[int] = None,
    error_message: Optional[str] = None,
) -> dict[str, Any]:
    """Insert a post log entry."""
    cursor = await db.execute(
        """
        INSERT INTO post_log (rule_id, channel_id, provider_type, content,
                              status, platform, telegram_message_id, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (rule_id, channel_id, provider_type, content, status, platform, telegram_message_id, error_message),
    )
    log_id = cursor.lastrowid
    row = await db.fetchone("SELECT * FROM post_log WHERE id = ?", (log_id,))
    return row  # type: ignore[return-value]


async def get_post_logs_by_user(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent post logs for a user (joins through rules)."""
    return await db.fetchall(
        """
        SELECT pl.* FROM post_log pl
        INNER JOIN rules r ON pl.rule_id = r.id
        WHERE r.user_id = ?
        ORDER BY pl.created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )


async def get_post_logs_by_rule(rule_id: int, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent post logs for a specific rule."""
    return await db.fetchall(
        "SELECT * FROM post_log WHERE rule_id = ? ORDER BY created_at DESC LIMIT ?",
        (rule_id, limit),
    )


async def get_recent_posts(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent post logs across all users."""
    return await db.fetchall(
        "SELECT * FROM post_log ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


# ===========================================================================
# Webhook Events
# ===========================================================================

_WEBHOOK_JSON_FIELDS = ("payload",)


async def create_webhook_event(data: WebhookEventCreate) -> dict[str, Any]:
    """Insert a new incoming webhook event."""
    cursor = await db.execute(
        """
        INSERT INTO webhook_events (provider_id, payload, source_ip)
        VALUES (?, ?, ?)
        """,
        (data.provider_id, _json_dumps(data.payload), data.source_ip),
    )
    event_id = cursor.lastrowid
    row = await db.fetchone("SELECT * FROM webhook_events WHERE id = ?", (event_id,))
    return _deserialize_row(row, _WEBHOOK_JSON_FIELDS)  # type: ignore[return-value]


async def get_unprocessed_events(limit: int = 100) -> list[dict[str, Any]]:
    """Return webhook events that have not yet been processed."""
    rows = await db.fetchall(
        "SELECT * FROM webhook_events WHERE processed = 0 ORDER BY created_at ASC LIMIT ?",
        (limit,),
    )
    return _deserialize_rows(rows, _WEBHOOK_JSON_FIELDS)


async def mark_event_processed(event_id: int) -> None:
    """Mark a webhook event as processed."""
    await db.execute(
        "UPDATE webhook_events SET processed = 1 WHERE id = ?",
        (event_id,),
    )
