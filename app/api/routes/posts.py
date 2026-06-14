"""Posts and Webhook API routes."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import crud
from app.database.models import PostLogResponse, WebhookEventCreate
from app.api.deps import get_current_user, verify_webhook_secret
from app.config import settings

router = APIRouter(prefix="/posts", tags=["posts"])
webhook_router = APIRouter(prefix="/webhook", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Posts endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[PostLogResponse])
async def list_posts(
    limit: int = 20,
    rule_id: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    """List user's post logs."""
    if rule_id:
        # Verify the rule belongs to the user before returning its logs
        rule = await crud.get_rule_by_id(rule_id)
        if not rule or rule["user_id"] != user["id"]:
            raise HTTPException(status_code=404, detail="Rule not found")
        return await crud.get_post_logs_by_rule(rule_id, limit=limit)
    return await crud.get_post_logs_by_user(user["id"], limit=limit)


@router.get("/stats")
async def post_stats(user: dict = Depends(get_current_user)):
    """Get post statistics."""
    recent = await crud.get_post_logs_by_user(user["id"], limit=100)
    total = len(recent)
    sent = sum(1 for p in recent if p["status"] == "sent")
    failed = sum(1 for p in recent if p["status"] == "failed")
    telegram = sum(1 for p in recent if p["platform"] == "telegram")
    twitter = sum(1 for p in recent if p["platform"] == "twitter")

    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "telegram": telegram,
        "twitter": twitter,
        "success_rate": round(sent / total * 100, 1) if total > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------


@webhook_router.post("/{provider_id}")
async def receive_webhook(
    provider_id: int,
    request: Request,
    verified: bool = Depends(verify_webhook_secret),
):
    """Receive webhook data for a provider."""
    provider = await crud.get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if provider["provider_type"] != "webhook":
        raise HTTPException(status_code=400, detail="Provider is not a webhook type")

    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": (await request.body()).decode()}

    # Store webhook event
    event = await crud.create_webhook_event(
        data=WebhookEventCreate(
            provider_id=provider_id,
            payload=payload,
            source_ip=request.client.host if request.client else None,
        ),
    )

    return {"status": "received", "event_id": event["id"]}
