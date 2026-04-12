from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core import security
from app.dependencies import get_platform_service
from app.schemas import AuthTokenRequest
from app.services import PlatformService

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check(platform: PlatformService = Depends(get_platform_service)):
    security_payload = {
        "write_api_key_required": bool(security.WRITE_API_KEY),
        "write_jwt_enabled": bool(security.WRITE_JWT_SECRET),
        "write_jwt_required_roles": sorted(security.WRITE_JWT_REQUIRED_ROLES),
        "write_rate_limit_per_minute": security.WRITE_RATE_LIMIT_PER_MIN,
        "ws_auth_required": security.WS_AUTH_REQUIRED,
    }
    return platform.health_payload(security_payload)


@router.get("/health/live")
async def health_live():
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(platform: PlatformService = Depends(get_platform_service)):
    payload = platform.readiness_payload()
    if payload["status"] != "ready":
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.post("/auth/token")
async def issue_token(
    request: AuthTokenRequest,
    _: None = Depends(security.verify_token_issuance_access),
):
    return security.generate_access_token(
        subject=request.subject,
        expires_in_minutes=request.expires_in_minutes,
    )
