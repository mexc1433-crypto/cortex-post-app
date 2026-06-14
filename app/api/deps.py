"""FastAPI dependencies."""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import crud
from app.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Get current user from request.
    For Mini App: uses initData from Telegram WebApp.
    For API: uses Bearer token (telegram_id for simplicity).
    """
    # Try to get user from Mini App init data
    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data:
        # Validate init data from Telegram Mini App
        # For production, validate with bot token hash
        # For now, extract user_id from init_data
        try:
            import hashlib
            import hmac
            from urllib.parse import parse_qs

            # Simple validation - in production use proper hash validation
            pairs = dict(x.split("=", 1) for x in init_data.split("&") if "=" in x)
            user_json = pairs.get("user", "")

            if user_json:
                import json
                from urllib.parse import unquote
                user_data = json.loads(unquote(user_json))
                telegram_id = user_data.get("id")
                if telegram_id:
                    user = await crud.get_user_by_telegram_id(telegram_id)
                    if user:
                        return user
        except Exception as e:
            logger.error(f"Init data parse error: {e}")

    # Try Bearer token (telegram_id as token for simplicity)
    if credentials:
        try:
            telegram_id = int(credentials.credentials)
            user = await crud.get_user_by_telegram_id(telegram_id)
            if user:
                return user
        except (ValueError, TypeError):
            pass

    raise HTTPException(status_code=401, detail="Unauthorized")


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


async def verify_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    """Verify user is admin."""
    if user["telegram_id"] not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def verify_webhook_secret(
    x_webhook_secret: Optional[str] = Header(None),
) -> bool:
    """Verify webhook secret for incoming webhooks."""
    if settings.WEBHOOK_SECRET and x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    return True
