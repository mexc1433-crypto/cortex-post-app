"""Subscription API routes."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.database import crud
from app.database.models import UserUpdate
from app.api.deps import get_current_user, verify_admin
from app.freemium import freemium

router = APIRouter(prefix="/subscription", tags=["subscription"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Subscription endpoints
# ---------------------------------------------------------------------------


@router.get("/limits")
async def get_limits(user: dict = Depends(get_current_user)):
    """Get current subscription limits and usage."""
    return await freemium.get_user_limits(user["id"])


@router.get("/info")
async def get_subscription_info(user: dict = Depends(get_current_user)):
    """Get subscription information."""
    return {
        "tier": user["tier"],
        "premium_expires_at": user.get("premium_expires_at"),
        "telegram_id": user["telegram_id"],
    }


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@admin_router.post("/upgrade/{telegram_id}")
async def upgrade_user(
    telegram_id: int,
    admin: dict = Depends(verify_admin),
):
    """Upgrade a user to premium (admin only)."""
    user = await crud.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await crud.update_user(
        user["id"],
        UserUpdate(
            tier="premium",
            premium_expires_at=datetime.utcnow() + timedelta(days=30),
        ),
    )

    return {"status": "upgraded", "telegram_id": telegram_id}


@admin_router.post("/downgrade/{telegram_id}")
async def downgrade_user(
    telegram_id: int,
    admin: dict = Depends(verify_admin),
):
    """Downgrade a user to free (admin only)."""
    user = await crud.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await crud.update_user(
        user["id"],
        UserUpdate(tier="free", premium_expires_at=None),
    )

    return {"status": "downgraded", "telegram_id": telegram_id}


@admin_router.get("/users")
async def list_users(
    admin: dict = Depends(verify_admin),
):
    """List all users (admin only)."""
    # Simple admin endpoint — use database directly for full listing
    return {"message": "Use database directly for user listing"}
