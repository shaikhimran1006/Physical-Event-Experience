"""Compatibility entrypoint exposing the modular FastAPI application."""

from app.main import app, platform_service
from app.core import security


# Backward-compatible exports used by tests and local scripts.
firestore_svc = platform_service.firestore_svc
pubsub_svc = platform_service.pubsub_svc
bq_svc = platform_service.bq_svc
prediction_svc = platform_service.prediction_svc
recommendation_svc = platform_service.recommendation_svc
notification_svc = platform_service.notification_svc
simulation_engine = platform_service.simulation_engine
ws_manager = platform_service.ws_manager

REQUESTED_USE_GCP = platform_service.requested_use_gcp
SERVICE_GCP_MODES = platform_service.service_gcp_modes
ACTIVE_USE_GCP = platform_service.active_use_gcp


def _invalidate_read_cache():
    platform_service.invalidate_cache()


def _encode_hs256_jwt(payload: dict, secret: str) -> str:
    return security.encode_hs256_jwt(payload, secret)


def _verify_hs256_jwt(token: str, secret: str) -> dict:
    return security.verify_hs256_jwt(token, secret)


def _sync_security_aliases() -> None:
    global WRITE_AUTH_REQUIRED
    global WRITE_API_KEY
    global WRITE_RATE_LIMIT_PER_MIN
    global WRITE_JWT_SECRET
    global WRITE_JWT_REQUIRED_ROLES
    global WS_AUTH_REQUIRED
    global TOKEN_ISSUER_SUBJECT_ROLES
    global _rate_limit_buckets

    WRITE_AUTH_REQUIRED = security.WRITE_AUTH_REQUIRED
    WRITE_API_KEY = security.WRITE_API_KEY
    WRITE_RATE_LIMIT_PER_MIN = security.WRITE_RATE_LIMIT_PER_MIN
    WRITE_JWT_SECRET = security.WRITE_JWT_SECRET
    WRITE_JWT_REQUIRED_ROLES = security.WRITE_JWT_REQUIRED_ROLES
    WS_AUTH_REQUIRED = security.WS_AUTH_REQUIRED
    TOKEN_ISSUER_SUBJECT_ROLES = security.TOKEN_ISSUER_SUBJECT_ROLES
    _rate_limit_buckets = security._rate_limit_buckets


_sync_security_aliases()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
