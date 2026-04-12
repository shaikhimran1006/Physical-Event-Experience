from typing import Literal, Optional

from pydantic import BaseModel, Field

EventPhase = Literal["pre_game", "in_game", "in_game_2", "halftime", "post_game"]
QueuePointType = Literal["gate", "concession", "restroom"]
InterventionActionType = Literal["approve", "dismiss"]
NotificationType = Literal["general", "gate_suggestion", "queue_alert", "exit_guidance"]
NotificationPriority = Literal["low", "normal", "high"]
SimulationMode = Literal["demo", "full"]


class CrowdEvent(BaseModel):
    venue_id: str = Field(default="stadium_01", min_length=1, max_length=100)
    zone_id: str = Field(min_length=1, max_length=64)
    occupancy_count: int = Field(ge=0, le=120000)
    delta: int = Field(default=0, ge=-50000, le=50000)
    source: str = Field(default="sensor", min_length=1, max_length=40)
    event_phase: EventPhase = "pre_game"


class QueuePredictionRequest(BaseModel):
    venue_id: str = Field(default="stadium_01", min_length=1, max_length=100)
    point_id: str = Field(min_length=1, max_length=64)
    point_type: QueuePointType = "gate"
    current_queue_length: int = Field(ge=0, le=20000)
    avg_wait_seconds: float = Field(default=0, ge=0, le=21600)
    throughput_per_min: float = Field(default=10.0, gt=0, le=5000)
    event_phase: EventPhase = "pre_game"


class InterventionRequest(BaseModel):
    venue_id: str = Field(default="stadium_01", min_length=1, max_length=100)
    zone_id: Optional[str] = Field(default=None, min_length=1, max_length=64)


class InterventionAction(BaseModel):
    action: InterventionActionType


class NotifyRequest(BaseModel):
    venue_id: str = Field(default="stadium_01", min_length=1, max_length=100)
    target_zones: list[str] = Field(default_factory=list, max_length=50)
    title: str = Field(min_length=1, max_length=140)
    body: str = Field(min_length=1, max_length=500)
    notification_type: NotificationType = "general"
    priority: NotificationPriority = "normal"


class SimulationStartRequest(BaseModel):
    mode: SimulationMode = "demo"
    speed_factor: int = Field(default=10, ge=1, le=120)
    venue_id: str = Field(default="stadium_01", min_length=1, max_length=100)


class AuthTokenRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    expires_in_minutes: int = Field(default=30, ge=1, le=1440)
