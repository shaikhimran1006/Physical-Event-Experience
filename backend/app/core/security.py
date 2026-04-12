import base64
import hashlib
import hmac
import json
import os
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from time import monotonic
from typing import Optional

from fastapi import Header, HTTPException, Request, WebSocket, WebSocketException, status


def _get_write_rate_limit() -> int:
    raw = os.getenv("WRITE_RATE_LIMIT_PER_MINUTE", "120").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 120
    return max(1, parsed)


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _parse_subject_roles(raw: str) -> dict[str, list[str]]:
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}

    parsed: dict[str, list[str]] = {}
    for subject, roles_value in data.items():
        if not isinstance(subject, str) or not subject.strip():
            continue

        if isinstance(roles_value, str):
            roles = {roles_value.strip()} if roles_value.strip() else set()
        elif isinstance(roles_value, list):
            roles = {
                str(role).strip()
                for role in roles_value
                if str(role).strip()
            }
        else:
            roles = set()

        if roles:
            parsed[subject.strip()] = sorted(roles)
    return parsed


def _get_ws_subprotocol_values(websocket: WebSocket) -> list[str]:
    raw = websocket.headers.get("sec-websocket-protocol", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


WRITE_API_KEY = os.getenv("WRITE_API_KEY", "").strip()
WRITE_AUTH_REQUIRED = _get_bool_env("WRITE_AUTH_REQUIRED", True)
WRITE_RATE_LIMIT_PER_MIN = _get_write_rate_limit()
WRITE_JWT_SECRET = os.getenv("WRITE_JWT_SECRET", "").strip()
WRITE_JWT_REQUIRED_ROLES = {
    role.strip()
    for role in os.getenv("WRITE_JWT_REQUIRED_ROLES", "admin,ops").split(",")
    if role.strip()
}

TOKEN_ISSUER_REQUIRED_ROLES = {
    role.strip()
    for role in os.getenv("TOKEN_ISSUER_REQUIRED_ROLES", "admin").split(",")
    if role.strip()
}
TOKEN_ISSUER_SUBJECT_ROLES = _parse_subject_roles(
    os.getenv(
        "TOKEN_ISSUER_SUBJECT_ROLES",
        '{"dashboard-service":["admin","ops"],"fan-service":["fan"]}',
    )
)

WS_AUTH_REQUIRED = _get_bool_env("WS_AUTH_REQUIRED", True)
WS_DASHBOARD_REQUIRED_ROLES = {
    role.strip()
    for role in os.getenv("WS_DASHBOARD_REQUIRED_ROLES", "admin,ops").split(",")
    if role.strip()
}
WS_FAN_REQUIRED_ROLES = {
    role.strip()
    for role in os.getenv("WS_FAN_REQUIRED_ROLES", "fan,ops,admin").split(",")
    if role.strip()
}

_rate_limit_lock = threading.Lock()
_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    with _rate_limit_lock:
        _rate_limit_buckets.clear()


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def encode_hs256_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def verify_hs256_jwt(token: str, secret: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid JWT format")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(signature_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(status_code=401, detail="Invalid JWT signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(status_code=401, detail="JWT missing exp")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if exp <= now_ts:
        raise HTTPException(status_code=401, detail="JWT has expired")

    return payload


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def has_required_roles(payload: dict, required_roles: set[str]) -> bool:
    if not required_roles:
        return True
    claim = payload.get("roles", payload.get("role", []))
    if isinstance(claim, str):
        roles = {claim}
    elif isinstance(claim, list):
        roles = {str(item) for item in claim}
    else:
        roles = set()
    return bool(roles & required_roles)


def _enforce_write_rate_limit(request: Request):
    client_host = request.client.host if request.client else "unknown"
    now = monotonic()
    window_seconds = 60

    with _rate_limit_lock:
        bucket = _rate_limit_buckets[client_host]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= WRITE_RATE_LIMIT_PER_MIN:
            raise HTTPException(status_code=429, detail="Write rate limit exceeded")
        bucket.append(now)


def _auth_not_configured_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Write authentication is required but not configured",
    )


def _validate_write_auth(
    x_api_key: Optional[str],
    authorization: Optional[str],
    required_roles: set[str],
    role_error_detail: str,
) -> None:
    bearer_token = extract_bearer_token(authorization)
    if WRITE_JWT_SECRET and bearer_token:
        payload = verify_hs256_jwt(bearer_token, WRITE_JWT_SECRET)
        if not has_required_roles(payload, required_roles):
            raise HTTPException(status_code=403, detail=role_error_detail)
        return

    if WRITE_API_KEY and x_api_key == WRITE_API_KEY:
        return

    if not WRITE_AUTH_REQUIRED:
        return

    if WRITE_JWT_SECRET:
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")

    if WRITE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    raise _auth_not_configured_error()


def verify_write_access(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _enforce_write_rate_limit(request)

    _validate_write_auth(
        x_api_key=x_api_key,
        authorization=authorization,
        required_roles=WRITE_JWT_REQUIRED_ROLES,
        role_error_detail="JWT does not include required role",
    )


def verify_token_issuance_access(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _enforce_write_rate_limit(request)

    _validate_write_auth(
        x_api_key=x_api_key,
        authorization=authorization,
        required_roles=TOKEN_ISSUER_REQUIRED_ROLES,
        role_error_detail="JWT does not include token issuer role",
    )


def get_trusted_roles_for_subject(subject: str) -> list[str]:
    normalized_subject = subject.strip()
    roles = TOKEN_ISSUER_SUBJECT_ROLES.get(normalized_subject)
    if not roles:
        raise HTTPException(
            status_code=403,
            detail="Token issuance denied for subject",
        )
    return roles


def generate_access_token(subject: str, expires_in_minutes: int) -> dict:
    if not WRITE_JWT_SECRET:
        raise HTTPException(status_code=503, detail="JWT auth is not enabled")

    roles = get_trusted_roles_for_subject(subject)

    now_ts = int(datetime.now(timezone.utc).timestamp())
    exp_ts = now_ts + (expires_in_minutes * 60)
    payload = {
        "sub": subject,
        "roles": roles,
        "iat": now_ts,
        "exp": exp_ts,
    }
    token = encode_hs256_jwt(payload, WRITE_JWT_SECRET)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in_minutes * 60,
        "roles": roles,
    }


def verify_websocket_access(websocket: WebSocket, required_roles: set[str] | None = None) -> None:
    if not WS_AUTH_REQUIRED:
        return

    authorization = websocket.headers.get("authorization")
    token = extract_bearer_token(authorization)
    api_key = websocket.headers.get("x-api-key")

    for protocol in _get_ws_subprotocol_values(websocket):
        if protocol.startswith("bearer.") and not token:
            token = protocol.removeprefix("bearer.")
        if protocol.startswith("apikey.") and not api_key:
            api_key = protocol.removeprefix("apikey.")

    if token and WRITE_JWT_SECRET:
        payload = verify_hs256_jwt(token, WRITE_JWT_SECRET)
        if not has_required_roles(payload, required_roles or set()):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="JWT missing required websocket role",
            )
        return

    if WRITE_API_KEY and api_key == WRITE_API_KEY:
        return

    raise WebSocketException(
        code=status.WS_1008_POLICY_VIOLATION,
        reason="WebSocket authentication failed",
    )
