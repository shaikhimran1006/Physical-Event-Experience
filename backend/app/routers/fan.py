from typing import Optional

from fastapi import APIRouter, Depends

from app.dependencies import get_platform_service
from app.services import PlatformService

router = APIRouter(tags=["fan"])


@router.get("/fan/{venue_id}/best-gate")
async def best_gate(
    venue_id: str,
    section: Optional[str] = None,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.best_gate(venue_id, section)


@router.get("/fan/{venue_id}/best-concession")
async def best_concession(
    venue_id: str,
    section: Optional[str] = None,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.best_concession(venue_id, section)


@router.get("/fan/{venue_id}/exit-guidance")
async def exit_guidance(
    venue_id: str,
    section: Optional[str] = None,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.exit_guidance(venue_id, section)
