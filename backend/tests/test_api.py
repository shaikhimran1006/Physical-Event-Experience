from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


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
    monkeypatch.setattr(main, "WRITE_API_KEY", "top-secret", raising=False)

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
