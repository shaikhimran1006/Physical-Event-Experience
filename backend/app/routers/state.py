from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_platform_service
from app.services import PlatformService

router = APIRouter(tags=["state"])


@router.get("/state/{venue_id}")
async def get_venue_state(venue_id: str, platform: PlatformService = Depends(get_platform_service)):
    return platform.get_venue_state(venue_id)


@router.get("/state/{venue_id}/zones")
async def get_zones(venue_id: str, platform: PlatformService = Depends(get_platform_service)):
    return platform.get_zones(venue_id)


@router.get("/state/{venue_id}/queues")
async def get_queues(venue_id: str, platform: PlatformService = Depends(get_platform_service)):
    return platform.get_queues(venue_id)


@router.get("/interventions/{venue_id}")
async def get_interventions(
    venue_id: str,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.get_interventions(venue_id, status, limit, offset)


@router.get("/kpis/{venue_id}")
async def get_kpis(venue_id: str, platform: PlatformService = Depends(get_platform_service)):
    return platform.get_kpis(venue_id)
