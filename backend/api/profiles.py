from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.models import ProfileCreateRequest
from core.services import services

router = APIRouter()


@router.get("/")
async def list_profiles():
    return [item.model_dump(mode="json") for item in services.profiles.list_profiles()]


@router.get("/{profile_id}")
async def get_profile(profile_id: str):
    profile = services.profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.model_dump(mode="json")


@router.post("/")
async def save_profile(request: ProfileCreateRequest):
    profile = services.profiles.save_profile(request)
    return profile.model_dump(mode="json")


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str):
    profile = services.profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.builtin:
        raise HTTPException(status_code=400, detail="Cannot delete built-in profile")
    services.profiles.delete_profile(profile_id)
    return {"deleted": profile_id}
