"""Providers API routes."""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from app.database import crud
from app.database.models import ProviderCreate, ProviderResponse
from app.api.deps import get_current_user
from app.freemium import freemium
from app.providers import get_available_provider_types, get_provider

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/types")
async def list_provider_types():
    """List available provider types."""
    return {"types": get_available_provider_types()}


@router.get("", response_model=List[ProviderResponse])
async def list_providers(
    provider_type: str = None,
    user: dict = Depends(get_current_user),
):
    """List user's providers, optionally filtered by provider_type."""
    providers = await crud.get_providers_by_user(user["id"])
    if provider_type:
        providers = [p for p in providers if p["provider_type"] == provider_type]
    # Parse config JSON — crud deserializes but guard against str
    for p in providers:
        if isinstance(p.get("config"), str):
            p["config"] = json.loads(p["config"])
    return providers


@router.post("", response_model=ProviderResponse, status_code=201)
async def create_provider(
    provider: ProviderCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new provider."""
    # Check webhook access
    if provider.provider_type == "webhook" and not await freemium.can_use_webhook(user["id"]):
        raise HTTPException(status_code=403, detail="Webhook is premium only")

    # Validate provider config
    prov = get_provider(provider.provider_type, provider.config)
    if prov and not await prov.validate_config():
        raise HTTPException(status_code=400, detail="Invalid provider configuration")

    result = await crud.create_provider(
        user_id=user["id"],
        data=ProviderCreate(
            provider_type=provider.provider_type,
            name=provider.name,
            config=provider.config,
            is_active=provider.is_active,
        ),
    )

    # crud already deserializes config via _deserialize_row, but guard
    if isinstance(result.get("config"), str):
        result["config"] = json.loads(result["config"])

    return result


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider_detail(provider_id: int, user: dict = Depends(get_current_user)):
    """Get provider details."""
    provider = await crud.get_provider_by_id(provider_id)
    if not provider or provider["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Provider not found")
    if isinstance(provider.get("config"), str):
        provider["config"] = json.loads(provider["config"])
    return provider


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, user: dict = Depends(get_current_user)):
    """Delete a provider."""
    provider = await crud.get_provider_by_id(provider_id)
    if not provider or provider["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Provider not found")
    await crud.delete_provider(provider_id)
    return {"status": "deleted"}


@router.post("/{provider_id}/test")
async def test_provider(provider_id: int, user: dict = Depends(get_current_user)):
    """Test a provider by fetching data."""
    provider = await crud.get_provider_by_id(provider_id)
    if not provider or provider["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Provider not found")

    config = provider.get("config", {})
    if isinstance(config, str):
        config = json.loads(config)

    prov = get_provider(provider["provider_type"], config)
    if not prov:
        raise HTTPException(status_code=400, detail="Unknown provider type")

    try:
        data = await prov.fetch()
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/{provider_id}/fields")
async def get_provider_fields(provider_id: int, user: dict = Depends(get_current_user)):
    """Get available fields for a provider."""
    provider = await crud.get_provider_by_id(provider_id)
    if not provider or provider["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Provider not found")

    config = provider.get("config", {})
    if isinstance(config, str):
        config = json.loads(config)

    prov = get_provider(provider["provider_type"], config)
    if not prov:
        raise HTTPException(status_code=400, detail="Unknown provider type")

    return {"fields": prov.get_available_fields()}
