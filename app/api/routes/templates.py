"""Templates API routes."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from app.database import crud
from app.database.models import TemplateCreate, TemplateResponse, TemplateUpdate
from app.api.deps import get_current_user
from app.freemium import freemium

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    provider_type: str = None,
    user: dict = Depends(get_current_user),
):
    """List user's templates, optionally filtered by provider_type."""
    templates = await crud.get_templates_by_user(user["id"])
    if provider_type:
        templates = [t for t in templates if t["provider_type"] == provider_type]
    return templates


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    template: TemplateCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new template."""
    if not await freemium.can_add_template(user["id"]):
        raise HTTPException(status_code=403, detail="Template limit reached. Upgrade to premium.")

    return await crud.create_template(
        user_id=user["id"],
        data=TemplateCreate(
            name=template.name,
            content=template.content,
            provider_type=template.provider_type,
            parse_mode=template.parse_mode,
        ),
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: int, user: dict = Depends(get_current_user)):
    """Get template details."""
    template = await crud.get_template_by_id(template_id)
    if not template or template["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_update: TemplateUpdate,
    user: dict = Depends(get_current_user),
):
    """Update a template."""
    template = await crud.get_template_by_id(template_id)
    if not template or template["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = template_update.model_dump(exclude_unset=True)
    if not update_data:
        return template

    return await crud.update_template(template_id, TemplateUpdate(**update_data))


@router.delete("/{template_id}")
async def delete_template(template_id: int, user: dict = Depends(get_current_user)):
    """Delete a template."""
    template = await crud.get_template_by_id(template_id)
    if not template or template["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Template not found")
    await crud.delete_template(template_id)
    return {"status": "deleted"}


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: int,
    sample_data: dict = None,
    user: dict = Depends(get_current_user),
):
    """Preview template with sample data."""
    template = await crud.get_template_by_id(template_id)
    if not template or template["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Template not found")

    from app.engine.template_engine import template_engine

    # Use sample data or provider-specific defaults
    if not sample_data:
        sample_data = {
            "crypto": {"coin": "BTC", "price": 50000, "price_change_24h": 2.5},
            "rss": {"title": "خبر جديد", "link": "https://example.com", "summary": "ملخص الخبر"},
            "sports": {"home_team": "الأهلي", "away_team": "الزمالك", "score_home": 2, "score_away": 1},
            "weather": {"city": "القاهرة", "temp": 30, "humidity": 50, "description": "صافي"},
            "religious": {
                "city": "القاهرة",
                "fajr": "04:30",
                "dhuhr": "12:00",
                "asr": "15:30",
                "maghrib": "18:15",
                "isha": "19:45",
            },
        }.get(template["provider_type"], {"data": "sample"})

    rendered = template_engine.render(template["content"], sample_data)
    variables = template_engine.get_variables(template["content"])
    return {"rendered": rendered, "variables": variables}
