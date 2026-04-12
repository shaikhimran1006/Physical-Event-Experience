from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone

import main
from app.core import security


client = TestClient(main.app)
AUTH_HEADERS = {"X-API-Key": "test-api-key"}


def _reset_local_store():
    if main.firestore_svc.use_gcp:
        return
    main.firestore_svc._store = {
        "zones": {},
        "queues": {},
        "interventions": {},
        "notifications": {},
        "kpis": {},
    }
    main._invalidate_read_cache()
    security.reset_rate_limits()
    security.WRITE_AUTH_REQUIRED = True
    security.WRITE_API_KEY = AUTH_HEADERS["X-API-Key"]
    security.WRITE_JWT_SECRET = ""
    security.WRITE_JWT_REQUIRED_ROLES = {"admin", "ops"}


def test_health_endpoint_includes_security_metadata():
    _reset_local_store()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "security" in payload
    assert "write_rate_limit_per_minute" in payload["security"]


def test_ingest_crowd_rejects_negative_occupancy():
    _reset_local_store()
    response = client.post(
        "/ingest/crowd",
        headers=AUTH_HEADERS,
        json={
            "venue_id": "stadium_01",
            "zone_id": "zone_A1",
            "occupancy_count": -1,
            "delta": 0,
            "source": "sensor",
            "event_phase": "pre_game",
        },
    )

    assert response.status_code == 422


def test_best_gate_prefers_shorter_wait_queue():
    _reset_local_store()

    client.post(
        "/ingest/queue",
        headers=AUTH_HEADERS,
        json={
            "venue_id": "stadium_01",
            "point_id": "gate_A",
            "point_type": "gate",
            "current_queue_length": 40,
            "avg_wait_seconds": 600,
            "throughput_per_min": 8,
            "event_phase": "pre_game",
        },
    )
    client.post(
        "/ingest/queue",
        headers=AUTH_HEADERS,
        json={
            "venue_id": "stadium_01",
            "point_id": "gate_B",
            "point_type": "gate",
            "current_queue_length": 8,
            "avg_wait_seconds": 60,
            "throughput_per_min": 12,
            "event_phase": "pre_game",
        },
    )

    response = client.get("/fan/stadium_01/best-gate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["best_gate"] == "gate_B"


def test_write_endpoint_requires_api_key_when_enabled(monkeypatch):
    _reset_local_store()
    monkeypatch.setattr(security, "WRITE_API_KEY", "top-secret", raising=False)

    denied = client.post(
        "/ingest/crowd",
        json={
            "venue_id": "stadium_01",
            "zone_id": "zone_A1",
            "occupancy_count": 10,
            "delta": 1,
            "source": "sensor",
            "event_phase": "pre_game",
        },
    )
    assert denied.status_code == 401

    allowed = client.post(
        "/ingest/crowd",
        headers={"X-API-Key": "top-secret"},
        json={
            "venue_id": "stadium_01",
            "zone_id": "zone_A1",
            "occupancy_count": 12,
            "delta": 2,
            "source": "sensor",
            "event_phase": "pre_game",
        },
    )
    assert allowed.status_code == 200


def test_write_endpoint_accepts_valid_jwt(monkeypatch):
    _reset_local_store()
    monkeypatch.setattr(security, "WRITE_API_KEY", "", raising=False)
    monkeypatch.setattr(security, "WRITE_JWT_SECRET", "jwt-secret", raising=False)
    monkeypatch.setattr(security, "WRITE_JWT_REQUIRED_ROLES", {"ops"}, raising=False)

    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = security.encode_hs256_jwt(
        {
            "sub": "ops-user",
            "roles": ["ops"],
            "iat": now_ts,
            "exp": now_ts + 600,
        },
        "jwt-secret",
    )

    response = client.post(
        "/ingest/crowd",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "venue_id": "stadium_01",
            "zone_id": "zone_A1",
            "occupancy_count": 12,
            "delta": 2,
            "source": "sensor",
            "event_phase": "pre_game",
        },
    )

    assert response.status_code == 200


def test_write_endpoint_rejects_jwt_without_required_role(monkeypatch):
    _reset_local_store()
    monkeypatch.setattr(security, "WRITE_API_KEY", "", raising=False)
    monkeypatch.setattr(security, "WRITE_JWT_SECRET", "jwt-secret", raising=False)
    monkeypatch.setattr(security, "WRITE_JWT_REQUIRED_ROLES", {"admin"}, raising=False)

    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = security.encode_hs256_jwt(
        {
            "sub": "ops-user",
            "roles": ["ops"],
            "iat": now_ts,
            "exp": now_ts + 600,
        },
        "jwt-secret",
    )

    response = client.post(
        "/ingest/crowd",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "venue_id": "stadium_01",
            "zone_id": "zone_A1",
            "occupancy_count": 12,
            "delta": 2,
            "source": "sensor",
            "event_phase": "pre_game",
        },
    )

    assert response.status_code == 403


def test_interventions_endpoint_supports_limit_and_offset():
    _reset_local_store()
    base = datetime.now(timezone.utc)
    for idx in range(5):
        intervention_id = f"int_{idx}"
        main.firestore_svc.create_intervention(
            intervention_id,
            {
                "intervention_id": intervention_id,
                "venue_id": "stadium_01",
                "status": "pending",
                "recommendation": f"rec-{idx}",
                "created_at": (base + timedelta(seconds=idx)).isoformat(),
            },
        )

    response = client.get("/interventions/stadium_01?limit=2&offset=1")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["intervention_id"] == "int_3"
    assert payload[1]["intervention_id"] == "int_2"
