from fastapi import APIRouter, Depends

from app.core.security import verify_write_access
from app.dependencies import get_platform_service
from app.schemas import SimulationStartRequest
from app.services import PlatformService

router = APIRouter(tags=["simulation"])


@router.post("/simulation/start", dependencies=[Depends(verify_write_access)])
async def start_simulation(
    req: SimulationStartRequest,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.start_simulation(req)


@router.post("/simulation/stop", dependencies=[Depends(verify_write_access)])
async def stop_simulation(platform: PlatformService = Depends(get_platform_service)):
    return platform.stop_simulation()


@router.get("/simulation/status")
async def simulation_status(platform: PlatformService = Depends(get_platform_service)):
    return platform.simulation_status()
