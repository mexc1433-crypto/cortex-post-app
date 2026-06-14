"""Rules API routes."""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from app.database import crud
from app.database.models import RuleCreate, RuleResponse, RuleUpdate
from app.api.deps import get_current_user
from app.freemium import freemium

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=List[RuleResponse])
async def list_rules(user: dict = Depends(get_current_user)):
    """List user's rules."""
    rules = await crud.get_rules_by_user(user["id"])
    # Parse conditions JSON — crud already deserializes but guard against str
    for rule in rules:
        if isinstance(rule.get("conditions"), str):
            rule["conditions"] = json.loads(rule["conditions"])
    return rules


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(
    rule: RuleCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new rule."""
    if not await freemium.can_add_rule(user["id"]):
        raise HTTPException(status_code=403, detail="Rule limit reached. Upgrade to premium.")

    # Verify provider, template, channel belong to user
    provider = await crud.get_provider_by_id(rule.provider_id)
    if not provider or provider["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Provider not found")

    template = await crud.get_template_by_id(rule.template_id)
    if not template or template["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Template not found")

    channel = await crud.get_channel_by_id(rule.channel_id)
    if not channel or channel["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Channel not found")

    return await crud.create_rule(
        user_id=user["id"],
        data=RuleCreate(
            name=rule.name,
            provider_id=rule.provider_id,
            template_id=rule.template_id,
            channel_id=rule.channel_id,
            conditions=rule.conditions,
            condition_logic=rule.condition_logic,
            is_active=rule.is_active,
            cooldown_minutes=rule.cooldown_minutes,
            priority=rule.priority,
        ),
    )


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: int, user: dict = Depends(get_current_user)):
    """Get rule details."""
    rule = await crud.get_rule_by_id(rule_id)
    if not rule or rule["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Rule not found")
    if isinstance(rule.get("conditions"), str):
        rule["conditions"] = json.loads(rule["conditions"])
    return rule


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: int,
    rule_update: RuleUpdate,
    user: dict = Depends(get_current_user),
):
    """Update a rule."""
    rule = await crud.get_rule_by_id(rule_id)
    if not rule or rule["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = rule_update.model_dump(exclude_unset=True)
    if not update_data:
        # Nothing to update — return current state
        if isinstance(rule.get("conditions"), str):
            rule["conditions"] = json.loads(rule["conditions"])
        return rule

    # crud.update_rule accepts a RuleUpdate model and handles
    # conditions JSON serialization internally.
    result = await crud.update_rule(rule_id, rule_update)
    if result and isinstance(result.get("conditions"), str):
        result["conditions"] = json.loads(result["conditions"])
    return result


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, user: dict = Depends(get_current_user)):
    """Delete a rule."""
    rule = await crud.get_rule_by_id(rule_id)
    if not rule or rule["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Rule not found")
    await crud.delete_rule(rule_id)
    return {"status": "deleted"}


@router.post("/{rule_id}/trigger")
async def trigger_rule(rule_id: int, user: dict = Depends(get_current_user)):
    """Manually trigger a rule."""
    rule = await crud.get_rule_by_id(rule_id)
    if not rule or rule["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Rule not found")

    from app.engine.scheduler import cortex_scheduler
    await cortex_scheduler.trigger_rule_now(rule_id)
    return {"status": "triggered", "rule_id": rule_id}
