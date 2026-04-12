import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

import main
from app.core import security
from app.schemas import (
    CrowdEvent,
    InterventionAction,
    InterventionRequest,
    NotifyRequest,
    QueuePredictionRequest,
    SimulationStartRequest,
)

AUTH_HEADERS = {"X-API-Key": "test-api-key"}


@pytest.fixture(autouse=True)
def reset_platform_state():
    platform = main.platform_service

    if not platform.firestore_svc.use_gcp:
        platform.firestore_svc._store = {
            "zones": {},
            "queues": {},
            "interventions": {},
            "notifications": {},
            "kpis": {},
        }

    platform.invalidate_cache()
    security.reset_rate_limits()
    security.WRITE_AUTH_REQUIRED = True
    security.WRITE_API_KEY = AUTH_HEADERS["X-API-Key"]
    security.WRITE_JWT_SECRET = ""
    security.WRITE_JWT_REQUIRED_ROLES = {"admin", "ops"}
    security.TOKEN_ISSUER_SUBJECT_ROLES = {
        "dashboard-service": ["admin", "ops"],
        "fan-service": ["fan"],
        "user": ["ops"],
    }
    security.WS_AUTH_REQUIRED = True

    platform.simulation_engine._running = False
    platform.simulation_engine._phase = "idle"

    class LoopStub:
        @staticmethod
        def is_running() -> bool:
            return False

    platform.set_event_loop(LoopStub())
    platform.mark_ready(True)
    yield


def test_system_routes_liveness_readiness_and_token_flow(monkeypatch):
    with TestClient(main.app) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "alive"

        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"

        main.platform_service.mark_ready(False)
        not_ready = client.get("/health/ready")
        assert not_ready.status_code == 503
        main.platform_service.mark_ready(True)

        disabled = client.post(
            "/auth/token",
            headers=AUTH_HEADERS,
            json={"subject": "user", "expires_in_minutes": 5},
        )
        assert disabled.status_code == 503

        monkeypatch.setattr(security, "WRITE_JWT_SECRET", "jwt-secret", raising=False)
        monkeypatch.setattr(security, "WRITE_API_KEY", "token-api", raising=False)

        denied = client.post(
            "/auth/token",
            json={"subject": "user", "expires_in_minutes": 5},
        )
        assert denied.status_code == 401

        monkeypatch.setattr(
            security,
            "TOKEN_ISSUER_SUBJECT_ROLES",
            {"user": ["ops"]},
            raising=False,
        )

        allowed = client.post(
            "/auth/token",
            headers={"X-API-Key": "token-api"},
            json={"subject": "user", "expires_in_minutes": 5},
        )
        assert allowed.status_code == 200
        assert allowed.json()["token_type"] == "bearer"


def test_platform_service_core_write_paths(monkeypatch):
    platform = main.platform_service

    crowd_result = platform.ingest_crowd_event(
        CrowdEvent(zone_id="zone_A1", occupancy_count=100, delta=10, source="sensor", event_phase="pre_game"),
        BackgroundTasks(),
    )
    assert crowd_result["status"] == "ingested"

    queue_result = platform.ingest_queue_event(
        QueuePredictionRequest(
            point_id="gate_A",
            point_type="gate",
            current_queue_length=20,
            avg_wait_seconds=120,
            throughput_per_min=8,
            event_phase="pre_game",
        ),
        BackgroundTasks(),
    )
    assert queue_result["status"] == "ingested"

    prediction = platform.predict_queue(
        QueuePredictionRequest(
            point_id="gate_A",
            point_type="gate",
            current_queue_length=25,
            avg_wait_seconds=180,
            throughput_per_min=8,
            event_phase="pre_game",
        )
    )
    assert prediction["point_id"] == "gate_A"

    monkeypatch.setattr(
        platform.recommendation_svc,
        "generate_interventions",
        lambda venue_id, current_state, zone_filter=None: [
            {
                "type": "reroute",
                "target_zone": "zone_A1",
                "severity": "high",
                "recommendation": "Redistribute crowd",
            }
        ],
    )

    rec_result = platform.recommend_intervention(
        InterventionRequest(venue_id="stadium_01"),
        BackgroundTasks(),
    )
    assert rec_result["count"] == 1

    with pytest.raises(HTTPException):
        platform.update_intervention("missing", InterventionAction(action="approve"))

    platform.firestore_svc.create_intervention(
        "int-1",
        {
            "intervention_id": "int-1",
            "venue_id": "stadium_01",
            "target_zone": "zone_A1",
            "status": "pending",
            "notification": {"title": "t", "body": "b", "type": "general"},
        },
    )

    sent = {"count": 0}

    def fake_send_to_zones(payload):
        sent["count"] += 1

    monkeypatch.setattr(platform.notification_svc, "send_to_zones", fake_send_to_zones)
    updated = platform.update_intervention("int-1", InterventionAction(action="approve"))
    assert updated["status"] == "approved"
    assert sent["count"] == 1


def test_platform_service_async_notification_and_broadcast(monkeypatch):
    platform = main.platform_service
    sent = {"fan": 0}

    async def fake_broadcast(client_type: str, message: dict):
        if client_type == "fan":
            sent["fan"] += 1

    monkeypatch.setattr(platform.ws_manager, "broadcast", fake_broadcast)

    async def _send_notification():
        return await platform.send_notification(
            NotifyRequest(
                venue_id="stadium_01",
                target_zones=["zone_A1"],
                title="Heads up",
                body="Queue moved",
            ),
            BackgroundTasks(),
        )

    payload = asyncio.run(_send_notification())
    assert payload["status"] == "sent"
    assert sent["fan"] == 1

    called = {"count": 0}

    async def fake_state_broadcast(venue_id: str):
        called["count"] += 1

    monkeypatch.setattr(platform, "broadcast_venue_state", fake_state_broadcast)

    class LoopRunning:
        @staticmethod
        def is_running() -> bool:
            return True

    def fake_run_coroutine_threadsafe(coro, loop):
        called["count"] += 1
        coro.close()
        return object()

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)
    platform.set_event_loop(LoopRunning())
    platform.trigger_broadcast("stadium_01")
    assert called["count"] >= 1


def test_platform_service_simulation_and_read_paths(monkeypatch):
    platform = main.platform_service

    monkeypatch.setattr(platform.simulation_engine, "run", lambda **kwargs: None)
    started = platform.start_simulation(
        SimulationStartRequest(mode="demo", speed_factor=5, venue_id="stadium_01")
    )
    assert started["status"] == "simulation_started"

    platform.simulation_engine._running = True
    already = platform.start_simulation(
        SimulationStartRequest(mode="demo", speed_factor=5, venue_id="stadium_01")
    )
    assert already["status"] == "already_running"

    platform.simulation_engine._running = False
    stopped = platform.stop_simulation()
    assert stopped["status"] == "simulation_stopped"

    platform.firestore_svc.update_queue_state(
        venue_id="stadium_01",
        point_id="gate_A",
        point_type="gate",
        queue_length=10,
        avg_wait_seconds=60,
        throughput_per_min=10,
    )
    platform.firestore_svc.update_queue_state(
        venue_id="stadium_01",
        point_id="conc_1",
        point_type="concession",
        queue_length=5,
        avg_wait_seconds=90,
        throughput_per_min=5,
    )

    assert "queues" in platform.get_venue_state("stadium_01")
    assert "gate_A" in platform.get_queues("stadium_01")
    assert isinstance(platform.get_zones("stadium_01"), dict)
    assert platform.best_gate("stadium_01", section="A1")["best_gate"] == "gate_A"
    assert platform.best_concession("stadium_01")["best_concession"] == "conc_1"
    assert "best_exit" in platform.exit_guidance("stadium_01")

    platform.firestore_svc._store["queues"] = {}
    platform.invalidate_cache()
    assert platform.best_gate("stadium_01")["recommendation"].startswith("No gate")
    assert platform.best_concession("stadium_01")["recommendation"].startswith("No concession")


def test_interventions_and_kpis_slice_reads():
    platform = main.platform_service
    base = datetime.now(timezone.utc)

    for idx in range(4):
        platform.firestore_svc.create_intervention(
            f"it-{idx}",
            {
                "intervention_id": f"it-{idx}",
                "venue_id": "stadium_01",
                "status": "pending",
                "recommendation": f"r-{idx}",
                "created_at": (base + timedelta(seconds=idx)).isoformat(),
            },
        )

    slice_items = platform.get_interventions("stadium_01", status="pending", limit=2, offset=1)
    assert len(slice_items) == 2

    platform.firestore_svc.update_kpis("stadium_01", {"ok": True})
    assert platform.get_kpis("stadium_01") == {"ok": True}


def test_routes_end_to_end_smoke_for_modular_endpoints(monkeypatch):
    with TestClient(main.app) as client:
        crowd = client.post(
            "/ingest/crowd",
            headers=AUTH_HEADERS,
            json={
                "venue_id": "stadium_01",
                "zone_id": "zone_B1",
                "occupancy_count": 123,
                "delta": 5,
                "source": "sensor",
                "event_phase": "pre_game",
            },
        )
        assert crowd.status_code == 200

        queue = client.post(
            "/ingest/queue",
            headers=AUTH_HEADERS,
            json={
                "venue_id": "stadium_01",
                "point_id": "gate_B",
                "point_type": "gate",
                "current_queue_length": 12,
                "avg_wait_seconds": 120,
                "throughput_per_min": 10,
                "event_phase": "pre_game",
            },
        )
        assert queue.status_code == 200

        prediction = client.post(
            "/predict/queue",
            headers=AUTH_HEADERS,
            json={
                "venue_id": "stadium_01",
                "point_id": "gate_B",
                "point_type": "gate",
                "current_queue_length": 15,
                "avg_wait_seconds": 150,
                "throughput_per_min": 10,
                "event_phase": "pre_game",
            },
        )
        assert prediction.status_code == 200

        recommendation = client.post(
            "/recommend/intervention",
            headers=AUTH_HEADERS,
            json={"venue_id": "stadium_01"},
        )
        assert recommendation.status_code == 200

        state = client.get("/state/stadium_01")
        assert state.status_code == 200

        zones = client.get("/state/stadium_01/zones")
        assert zones.status_code == 200

        queues = client.get("/state/stadium_01/queues")
        assert queues.status_code == 200

        interventions = client.get("/interventions/stadium_01?limit=10&offset=0")
        assert interventions.status_code == 200

        fan_gate = client.get("/fan/stadium_01/best-gate?section=A1")
        assert fan_gate.status_code == 200

        fan_conc = client.get("/fan/stadium_01/best-concession")
        assert fan_conc.status_code == 200

        fan_exit = client.get("/fan/stadium_01/exit-guidance")
        assert fan_exit.status_code == 200

        notify = client.post(
            "/notify",
            headers=AUTH_HEADERS,
            json={
                "venue_id": "stadium_01",
                "target_zones": ["zone_B1"],
                "title": "Queue update",
                "body": "Try another gate",
                "notification_type": "queue_alert",
                "priority": "normal",
            },
        )
        assert notify.status_code == 200

        monkeypatch.setattr(main.simulation_engine, "run", lambda **kwargs: None)
        started = client.post(
            "/simulation/start",
            headers=AUTH_HEADERS,
            json={"mode": "demo", "speed_factor": 10, "venue_id": "stadium_01"},
        )
        assert started.status_code == 200

        status = client.get("/simulation/status")
        assert status.status_code == 200

        stopped = client.post("/simulation/stop", headers=AUTH_HEADERS)
        assert stopped.status_code == 200
