from .fan import router as fan_router
from .ingest import router as ingest_router
from .simulation import router as simulation_router
from .state import router as state_router
from .system import router as system_router
from .ws import router as websocket_router

__all__ = [
    "fan_router",
    "ingest_router",
    "simulation_router",
    "state_router",
    "system_router",
    "websocket_router",
]
