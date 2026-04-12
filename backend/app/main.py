import asyncio
import warnings
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import allow_credentials, get_cors_origins
from app.core.observability import configure_logging, register_observability
from app.routers import (
    fan_router,
    ingest_router,
    simulation_router,
    state_router,
    system_router,
    websocket_router,
)
from app.services import PlatformService

load_dotenv()
configure_logging()

warnings.filterwarnings("ignore", message=r".*python_multipart.*", category=PendingDeprecationWarning)
warnings.filterwarnings("ignore", message=r".*on_event is deprecated, use lifespan event handlers instead\..*", category=DeprecationWarning)

platform_service = PlatformService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    platform_service.set_event_loop(asyncio.get_running_loop())
    platform_service.mark_ready(True)
    yield
    platform_service.mark_ready(False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stadium OS Copilot API",
        version="1.0.0",
        description="Real-time crowd intelligence and fan experience platform",
        lifespan=lifespan,
    )

    cors_origins = get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials(cors_origins),
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    register_observability(app)

    app.state.platform_service = platform_service

    app.include_router(system_router)
    app.include_router(ingest_router)
    app.include_router(simulation_router)
    app.include_router(state_router)
    app.include_router(fan_router)
    app.include_router(websocket_router)

    return app


app = create_app()
