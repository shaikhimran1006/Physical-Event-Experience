import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, WebSocketDisconnect, WebSocketException
from starlette.requests import Request

import main
from app.core import security
from app.routers.ws import websocket_dashboard, websocket_fan
from app.websocket.manager import ConnectionManager


def _make_request(client_host: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (client_host, 12345),
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
    }
    return Request(scope)


def _reset_security_state():
    security.reset_rate_limits()
    security.WRITE_AUTH_REQUIRED = True
    security.WRITE_API_KEY = ""
    security.WRITE_JWT_SECRET = ""
    security.WRITE_JWT_REQUIRED_ROLES = {"admin", "ops"}
    security.TOKEN_ISSUER_SUBJECT_ROLES = {
        "dashboard-service": ["admin", "ops"],
        "fan-service": ["fan"],
    }
    security.WS_AUTH_REQUIRED = True


class FakeWebSocket:
    def __init__(self, platform, messages=None, query_params=None, headers=None):
        self.app = SimpleNamespace(state=SimpleNamespace(platform_service=platform))
        self.query_params = query_params or {}
        self.headers = headers or {}
        self._messages = iter(messages or [])
        self.sent_messages = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        try:
            item = next(self._messages)
            if isinstance(item, Exception):
                raise item
            return item
        except StopIteration as exc:
            raise WebSocketDisconnect() from exc

    async def send_json(self, message):
        self.sent_messages.append(message)


@pytest.fixture(autouse=True)
def reset_state_each_test():
    _reset_security_state()
    if not main.firestore_svc.use_gcp:
        main.firestore_svc._store = {
            "zones": {},
            "queues": {},
            "interventions": {},
            "notifications": {},
            "kpis": {},
        }
    main._invalidate_read_cache()
    yield
    _reset_security_state()


def test_jwt_encode_and_verify_roundtrip():
    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = security.encode_hs256_jwt(
        {"sub": "user", "roles": ["ops"], "iat": now_ts, "exp": now_ts + 120},
        "secret",
    )
    payload = security.verify_hs256_jwt(token, "secret")
    assert payload["sub"] == "user"


def test_jwt_verify_rejects_bad_inputs():
    with pytest.raises(HTTPException):
        security.verify_hs256_jwt("bad-token", "secret")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = security.encode_hs256_jwt(
        {"sub": "user", "roles": ["ops"], "iat": now_ts, "exp": now_ts + 60},
        "secret-a",
    )
    with pytest.raises(HTTPException):
        security.verify_hs256_jwt(token, "secret-b")

    token_no_exp = security.encode_hs256_jwt({"sub": "user"}, "secret")
    with pytest.raises(HTTPException):
        security.verify_hs256_jwt(token_no_exp, "secret")

    expired = security.encode_hs256_jwt(
        {"sub": "user", "roles": ["ops"], "iat": now_ts - 600, "exp": now_ts - 1},
        "secret",
    )
    with pytest.raises(HTTPException):
        security.verify_hs256_jwt(expired, "secret")


def test_extract_bearer_and_roles_helpers():
    assert security.extract_bearer_token(None) is None
    assert security.extract_bearer_token("Basic abc") is None
    assert security.extract_bearer_token("Bearer token-value") == "token-value"

    assert security.has_required_roles({"roles": ["ops"]}, {"ops"}) is True
    assert security.has_required_roles({"roles": "admin"}, {"admin"}) is True
    assert security.has_required_roles({"roles": ["guest"]}, {"admin"}) is False


def test_verify_write_access_rate_limit_and_api_key(monkeypatch):
    request = _make_request("rate-limited-client")

    monkeypatch.setattr(security, "WRITE_RATE_LIMIT_PER_MIN", 1, raising=False)
    monkeypatch.setattr(security, "WRITE_API_KEY", "top-secret", raising=False)
    monkeypatch.setattr(security, "WRITE_JWT_SECRET", "", raising=False)

    with pytest.raises(HTTPException) as first_error:
        security.verify_write_access(request, x_api_key=None, authorization=None)
    assert first_error.value.status_code == 401

    with pytest.raises(HTTPException) as second_error:
        security.verify_write_access(request, x_api_key=None, authorization=None)
    assert second_error.value.status_code == 429

    security.reset_rate_limits()
    ok_request = _make_request("api-key-client")
    security.verify_write_access(ok_request, x_api_key="top-secret", authorization=None)


def test_verify_write_access_jwt_paths(monkeypatch):
    request = _make_request("jwt-client")

    monkeypatch.setattr(security, "WRITE_API_KEY", "", raising=False)
    monkeypatch.setattr(security, "WRITE_JWT_SECRET", "jwt-secret", raising=False)
    monkeypatch.setattr(security, "WRITE_JWT_REQUIRED_ROLES", {"admin"}, raising=False)

    now_ts = int(datetime.now(timezone.utc).timestamp())
    bad_role_token = security.encode_hs256_jwt(
        {"sub": "ops", "roles": ["ops"], "iat": now_ts, "exp": now_ts + 60},
        "jwt-secret",
    )
    with pytest.raises(HTTPException) as role_error:
        security.verify_write_access(request, x_api_key=None, authorization=f"Bearer {bad_role_token}")
    assert role_error.value.status_code == 403

    good_token = security.encode_hs256_jwt(
        {"sub": "admin", "roles": ["admin"], "iat": now_ts, "exp": now_ts + 60},
        "jwt-secret",
    )
    security.verify_write_access(request, x_api_key=None, authorization=f"Bearer {good_token}")


def test_generate_access_token_and_websocket_access(monkeypatch):
    monkeypatch.setattr(security, "WRITE_JWT_SECRET", "jwt-secret", raising=False)
    monkeypatch.setattr(
        security,
        "TOKEN_ISSUER_SUBJECT_ROLES",
        {"subj": ["ops"]},
        raising=False,
    )
    token_payload = security.generate_access_token("subj", 5)
    assert token_payload["token_type"] == "bearer"

    token = token_payload["access_token"]

    monkeypatch.setattr(security, "WS_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(security, "WRITE_API_KEY", "api-secret", raising=False)

    ws_jwt = SimpleNamespace(headers={"authorization": f"Bearer {token}"})
    security.verify_websocket_access(ws_jwt, {"ops"})

    ws_api_key = SimpleNamespace(headers={"x-api-key": "api-secret"})
    security.verify_websocket_access(ws_api_key, {"ops"})

    ws_bad = SimpleNamespace(headers={})
    with pytest.raises(WebSocketException):
        security.verify_websocket_access(ws_bad, {"ops"})


def test_websocket_manager_connect_broadcast_disconnect():
    manager = ConnectionManager()

    class DummySocket:
        def __init__(self, fail=False):
            self.fail = fail
            self.accepted = False
            self.messages = []

        async def accept(self):
            self.accepted = True

        async def send_json(self, payload):
            if self.fail:
                raise RuntimeError("socket down")
            self.messages.append(payload)

    ws_ok = DummySocket()
    ws_fail = DummySocket(fail=True)

    asyncio.run(manager.connect(ws_ok, "dashboard"))
    asyncio.run(manager.connect(ws_fail, "dashboard"))
    asyncio.run(manager.broadcast("dashboard", {"kind": "ping"}))

    assert ws_ok.accepted is True
    assert ws_ok.messages[-1]["kind"] == "ping"
    assert ws_fail not in manager.active_connections["dashboard"]

    asyncio.run(manager.broadcast_all({"kind": "all"}))
    assert ws_ok.messages[-1]["kind"] == "all"

    manager.disconnect(ws_ok, "dashboard")
    assert ws_ok not in manager.active_connections["dashboard"]


@pytest.mark.asyncio
async def test_websocket_routers_dashboard_and_fan(monkeypatch):
    platform = main.platform_service
    platform.ws_manager = ConnectionManager()

    security.WS_AUTH_REQUIRED = False

    dashboard_ws = FakeWebSocket(platform, messages=['{"type":"ping"}'])
    fan_ws = FakeWebSocket(platform, messages=['{"type":"ping"}', '{"type":"set_section","section":"A1"}'])

    await websocket_dashboard(dashboard_ws, "stadium_01")
    await websocket_fan(fan_ws, "stadium_01")

    dashboard_types = {msg.get("type") for msg in dashboard_ws.sent_messages}
    fan_types = {msg.get("type") for msg in fan_ws.sent_messages}

    assert "state_update" in dashboard_types
    assert "pong" in dashboard_types
    assert "fan_update" in fan_types
    assert "section_ack" in fan_types


@pytest.mark.asyncio
async def test_websocket_dashboard_invalid_json_and_generic_error_branch():
    platform = main.platform_service
    platform.ws_manager = ConnectionManager()

    security.WS_AUTH_REQUIRED = False

    ws = FakeWebSocket(platform, messages=["{not-json", RuntimeError("socket read failed")])

    await websocket_dashboard(ws, "stadium_01")

    sent_types = {msg.get("type") for msg in ws.sent_messages}
    assert "state_update" in sent_types
    assert "pong" not in sent_types
    assert ws not in platform.ws_manager.active_connections["dashboard"]


@pytest.mark.asyncio
async def test_websocket_fan_invalid_json_and_generic_error_branch():
    platform = main.platform_service
    platform.ws_manager = ConnectionManager()

    security.WS_AUTH_REQUIRED = False

    ws = FakeWebSocket(platform, messages=["{not-json", RuntimeError("socket read failed")])

    await websocket_fan(ws, "stadium_01")

    sent_types = {msg.get("type") for msg in ws.sent_messages}
    assert "fan_update" in sent_types
    assert "pong" not in sent_types
    assert "section_ack" not in sent_types
    assert ws not in platform.ws_manager.active_connections["fan"]
