from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.security import verify_write_access
from app.dependencies import get_platform_service
from app.schemas import (
    CrowdEvent,
    InterventionAction,
    InterventionRequest,
    NotifyRequest,
    QueuePredictionRequest,
)
from app.services import PlatformService

router = APIRouter(tags=["ingest"])


@router.post("/ingest/crowd", dependencies=[Depends(verify_write_access)])
async def ingest_crowd_event(
    event: CrowdEvent,
    background_tasks: BackgroundTasks,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.ingest_crowd_event(event, background_tasks)


@router.post("/ingest/queue", dependencies=[Depends(verify_write_access)])
async def ingest_queue_event(
    event: QueuePredictionRequest,
    background_tasks: BackgroundTasks,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.ingest_queue_event(event, background_tasks)


@router.post("/predict/queue", dependencies=[Depends(verify_write_access)])
async def predict_queue(
    req: QueuePredictionRequest,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.predict_queue(req)


@router.post("/recommend/intervention", dependencies=[Depends(verify_write_access)])
async def recommend_intervention(
    req: InterventionRequest,
    background_tasks: BackgroundTasks,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.recommend_intervention(req, background_tasks)


@router.put("/interventions/{intervention_id}", dependencies=[Depends(verify_write_access)])
async def update_intervention(
    intervention_id: str,
    action: InterventionAction,
    platform: PlatformService = Depends(get_platform_service),
):
    return platform.update_intervention(intervention_id, action)


@router.post("/notify", dependencies=[Depends(verify_write_access)])
async def send_notification(
    req: NotifyRequest,
    background_tasks: BackgroundTasks,
    platform: PlatformService = Depends(get_platform_service),
):
    return await platform.send_notification(req, background_tasks)
