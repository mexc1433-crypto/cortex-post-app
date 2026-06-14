"""Channels API routes."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from app.database import crud
from app.database.models import ChannelCreate, ChannelResponse, ChannelUpdate
from app.api.deps import get_current_user
from app.freemium import freemium

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=List[ChannelResponse])
async def list_channels(user: dict = Depends(get_current_user)):
    """List user's channels."""
    return await crud.get_channels_by_user(user["id"])


@router.post("", response_model=ChannelResponse, status_code=201)
async def create_channel(
    channel: ChannelCreate,
    user: dict = Depends(get_current_user),
):
    """Add a new channel."""
    if not await freemium.can_add_channel(user["id"]):
        raise HTTPException(status_code=403, detail="Channel limit reached. Upgrade to premium.")

    return await crud.create_channel(
        user_id=user["id"],
        data=ChannelCreate(
            channel_telegram_id=channel.channel_telegram_id,
            channel_title=channel.channel_title,
            channel_username=channel.channel_username,
            channel_type=channel.channel_type,
        ),
    )


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: int, user: dict = Depends(get_current_user)):
    """Get channel details."""
    channel = await crud.get_channel_by_id(channel_id)
    if not channel or channel["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.delete("/{channel_id}")
async def delete_channel(channel_id: int, user: dict = Depends(get_current_user)):
    """Delete a channel."""
    channel = await crud.get_channel_by_id(channel_id)
    if not channel or channel["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Channel not found")
    await crud.delete_channel(channel_id)
    return {"status": "deleted"}


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    user: dict = Depends(get_current_user),
):
    """Update channel settings."""
    channel = await crud.get_channel_by_id(channel_id)
    if not channel or channel["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Channel not found")

    update_data = channel_update.model_dump(exclude_unset=True)
    if not update_data:
        return channel

    return await crud.update_channel(channel_id, ChannelUpdate(**update_data))
