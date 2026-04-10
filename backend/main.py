"""
Stadium OS Copilot — FastAPI Backend
Real-time crowd intelligence + fan experience platform.
"""

import os
import uuid
import asyncio
import threading
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from services.firestore_service import FirestoreService
from services.pubsub_service import PubSubService
from services.bigquery_service import BigQueryService
from services.prediction_service import PredictionService
from services.recommendation_service import RecommendationService
from services.notification_service import NotificationService
from simulation.event_generator import SimulationEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App Init
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Stadium OS Copilot API",
    version="1.0.0",
    description="Real-time crowd intelligence and fan experience platform",
)

LOCAL_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]


def _get_cors_origins() -> list[str]:
    """Read CORS origins from env (comma-separated), fallback to local dev origins."""
    raw_origins = os.getenv("CORS_ORIGINS", "").strip()
    if not raw_origins:
        return LOCAL_CORS_ORIGINS
    if raw_origins == "*":
        return ["*"]
    return [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]


CORS_ORIGINS = _get_cors_origins()
ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Service singletons (lazy-init to support local dev without GCP)
# ---------------------------------------------------------------------------
REQUESTED_USE_GCP = os.getenv("USE_GCP", "false").lower() == "true"

firestore_svc = FirestoreService(use_gcp=REQUESTED_USE_GCP)
pubsub_svc = PubSubService(use_gcp=REQUESTED_USE_GCP)
bq_svc = BigQueryService(use_gcp=REQUESTED_USE_GCP)
prediction_svc = PredictionService()
recommendation_svc = RecommendationService()
notification_svc = NotificationService(use_gcp=REQUESTED_USE_GCP)
simulation_engine = SimulationEngine(firestore_svc, prediction_svc, recommendation_svc, notification_svc)

SERVICE_GCP_MODES = {
    "firestore": firestore_svc.use_gcp,
    "pubsub": pubsub_svc.use_gcp,
    "bigquery": bq_svc.use_gcp,
    "notification": notification_svc.use_gcp,
}
ACTIVE_USE_GCP = any(SERVICE_GCP_MODES.values())

# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {
            "dashboard": [],
            "fan": [],
        }
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket, client_type: str):
        await websocket.accept()
        with self._lock:
            if client_type not in self.active_connections:
                self.active_connections[client_type] = []
            self.active_connections[client_type].append(websocket)
        logger.info(f"WebSocket connected: {client_type} ({len(self.active_connections[client_type])} total)")

    def disconnect(self, websocket: WebSocket, client_type: str):
        with self._lock:
            if client_type in self.active_connections:
                self.active_connections[client_type] = [
                    ws for ws in self.active_connections[client_type] if ws != websocket
                ]

    async def broadcast(self, client_type: str, message: dict):
        """Broadcast a message to all connections of a given type."""
        with self._lock:
            connections = list(self.active_connections.get(client_type, []))
        dead = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        # Clean up dead connections
        for ws in dead:
            self.disconnect(ws, client_type)

    async def broadcast_all(self, message: dict):
        """Broadcast to all connected clients."""
        for client_type in list(self.active_connections.keys()):
            await self.broadcast(client_type, message)


ws_manager = ConnectionManager()

# Background task to push state updates via WebSocket
async def _broadcast_venue_state(venue_id: str):
    """Push current state to all WebSocket clients."""
    try:
        state = firestore_svc.get_venue_state(venue_id)
        kpis = firestore_svc.get_kpis(venue_id)
        interventions = firestore_svc.get_interventions(venue_id)
        sim_status = simulation_engine.get_status()

        dashboard_msg = {
            "type": "state_update",
            "venue_id": venue_id,
            "zones": state.get("zones", {}),
            "queues": state.get("queues", {}),
            "interventions": interventions[:20],
            "kpis": kpis,
            "simulation": sim_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await ws_manager.broadcast("dashboard", dashboard_msg)

        # Fan-specific data
        queues = state.get("queues", {})
        gates = {k: v for k, v in queues.items() if v.get("point_type") == "gate"}
        concessions = {k: v for k, v in queues.items() if v.get("point_type") == "concession"}

        best_gate_id = min(gates, key=lambda k: gates[k].get("avgWaitMinutes", 999)) if gates else None
        best_conc_id = min(concessions, key=lambda k: concessions[k].get("avgWaitMinutes", 999)) if concessions else None

        fan_msg = {
            "type": "fan_update",
            "venue_id": venue_id,
            "queues": queues,
            "best_gate": {
                "best_gate": best_gate_id,
                "wait_minutes": gates[best_gate_id].get("avgWaitMinutes", 0) if best_gate_id else 0,
                "all_gates": gates,
            } if best_gate_id else None,
            "best_concession": {
                "best_concession": best_conc_id,
                "wait_minutes": concessions[best_conc_id].get("avgWaitMinutes", 0) if best_conc_id else 0,
                "all_concessions": concessions,
            } if best_conc_id else None,
            "simulation": sim_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await ws_manager.broadcast("fan", fan_msg)
    except Exception as e:
        logger.error(f"WebSocket broadcast error: {e}")


# Store reference to the event loop for cross-thread broadcasting
_event_loop = None

@app.on_event("startup")
async def startup():
    global _event_loop
    _event_loop = asyncio.get_event_loop()


def trigger_broadcast(venue_id: str = "stadium_01"):
    """Thread-safe trigger for WebSocket broadcast (called from simulation thread)."""
    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast_venue_state(venue_id), _event_loop)


# Give the simulation engine a reference to the broadcast trigger
simulation_engine.set_broadcast_callback(trigger_broadcast)

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class CrowdEvent(BaseModel):
    venue_id: str = "stadium_01"
    zone_id: str
    occupancy_count: int
    delta: int = 0
    source: str = "sensor"
    event_phase: str = "pre_game"

class QueuePredictionRequest(BaseModel):
    venue_id: str = "stadium_01"
    point_id: str
    point_type: str = "gate"  # gate | concession | restroom
    current_queue_length: int
    avg_wait_seconds: float = 0
    throughput_per_min: float = 10.0
    event_phase: str = "pre_game"

class InterventionRequest(BaseModel):
    venue_id: str = "stadium_01"
    zone_id: Optional[str] = None  # If null, evaluate all zones

class InterventionAction(BaseModel):
    action: str  # "approve" | "dismiss"

class NotifyRequest(BaseModel):
    venue_id: str = "stadium_01"
    target_zones: list[str] = []
    title: str
    body: str
    notification_type: str = "general"  # gate_suggestion | queue_alert | exit_guidance
    priority: str = "normal"

class SimulationStartRequest(BaseModel):
    mode: str = "demo"          # demo | full
    speed_factor: int = 10      # 10x = 1 real sec per 10 sim secs
    venue_id: str = "stadium_01"

# ---------------------------------------------------------------------------
# WebSocket Endpoints
# ---------------------------------------------------------------------------

@app.websocket("/ws/dashboard/{venue_id}")
async def websocket_dashboard(websocket: WebSocket, venue_id: str):
    """WebSocket endpoint for ops dashboard — receives full state updates."""
    await ws_manager.connect(websocket, "dashboard")
    try:
        # Send initial state immediately
        await _broadcast_venue_state(venue_id)
        while True:
            # Keep connection alive, listen for commands
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "dashboard")
    except Exception:
        ws_manager.disconnect(websocket, "dashboard")


@app.websocket("/ws/fan/{venue_id}")
async def websocket_fan(websocket: WebSocket, venue_id: str):
    """WebSocket endpoint for fan app — receives personalized fan updates."""
    await ws_manager.connect(websocket, "fan")
    try:
        await _broadcast_venue_state(venue_id)
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "set_section":
                # Fan tells us their section for personalized recommendations
                section = msg.get("section", "")
                await websocket.send_json({
                    "type": "section_ack",
                    "section": section,
                    "message": f"Personalized recommendations for {section}",
                })
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "fan")
    except Exception:
        ws_manager.disconnect(websocket, "fan")


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Stadium OS Copilot API",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gcp_requested": REQUESTED_USE_GCP,
        "gcp_enabled": ACTIVE_USE_GCP,
        "gcp_services": SERVICE_GCP_MODES,
        "websocket_connections": {
            k: len(v) for k, v in ws_manager.active_connections.items()
        },
    }


@app.post("/ingest/crowd")
async def ingest_crowd_event(event: CrowdEvent, background_tasks: BackgroundTasks):
    """Ingest a crowd/occupancy event from sensors or turnstiles."""
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    payload = {
        "event_id": event_id,
        "venue_id": event.venue_id,
        "zone_id": event.zone_id,
        "timestamp": timestamp,
        "occupancy_count": event.occupancy_count,
        "delta": event.delta,
        "source": event.source,
        "event_phase": event.event_phase,
    }

    # Write to Firestore (real-time state)
    firestore_svc.update_zone_state(
        venue_id=event.venue_id,
        zone_id=event.zone_id,
        occupancy=event.occupancy_count,
        event_phase=event.event_phase,
    )

    # Publish to Pub/Sub + BigQuery in background
    background_tasks.add_task(pubsub_svc.publish, "crowd_events", payload)
    background_tasks.add_task(bq_svc.insert_crowd_event, payload)

    # Broadcast state update via WebSocket
    trigger_broadcast(event.venue_id)

    return {"event_id": event_id, "status": "ingested", "timestamp": timestamp}


@app.post("/ingest/queue")
async def ingest_queue_event(event: QueuePredictionRequest, background_tasks: BackgroundTasks):
    """Ingest a queue measurement event."""
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    payload = {
        "event_id": event_id,
        "venue_id": event.venue_id,
        "point_id": event.point_id,
        "point_type": event.point_type,
        "timestamp": timestamp,
        "queue_length": event.current_queue_length,
        "avg_wait_seconds": event.avg_wait_seconds,
        "throughput_per_min": event.throughput_per_min,
    }

    # Update Firestore
    firestore_svc.update_queue_state(
        venue_id=event.venue_id,
        point_id=event.point_id,
        point_type=event.point_type,
        queue_length=event.current_queue_length,
        avg_wait_seconds=event.avg_wait_seconds,
        throughput_per_min=event.throughput_per_min,
    )

    background_tasks.add_task(pubsub_svc.publish, "queue_events", payload)
    background_tasks.add_task(bq_svc.insert_queue_event, payload)

    trigger_broadcast(event.venue_id)

    return {"event_id": event_id, "status": "ingested"}


@app.post("/predict/queue")
async def predict_queue(req: QueuePredictionRequest):
    """Predict queue length and wait time for the next 15 minutes."""
    prediction = prediction_svc.predict_queue(
        point_id=req.point_id,
        current_queue_length=req.current_queue_length,
        avg_wait_seconds=req.avg_wait_seconds,
        throughput_per_min=req.throughput_per_min,
        event_phase=req.event_phase,
    )

    # Update Firestore with prediction
    firestore_svc.update_prediction(
        venue_id=req.venue_id,
        point_id=req.point_id,
        point_type=req.point_type,
        prediction=prediction,
    )

    return prediction


@app.post("/recommend/intervention")
async def recommend_intervention(req: InterventionRequest, background_tasks: BackgroundTasks):
    """Generate intervention recommendations based on current state."""
    current_state = firestore_svc.get_venue_state(req.venue_id)

    recommendations = recommendation_svc.generate_interventions(
        venue_id=req.venue_id,
        current_state=current_state,
        zone_filter=req.zone_id,
    )

    # Store interventions in Firestore
    for rec in recommendations:
        intervention_id = str(uuid.uuid4())
        rec["intervention_id"] = intervention_id
        rec["venue_id"] = req.venue_id
        rec["status"] = "pending"
        rec["created_at"] = datetime.now(timezone.utc).isoformat()
        firestore_svc.create_intervention(intervention_id, rec)
        background_tasks.add_task(pubsub_svc.publish, "interventions", rec)

    trigger_broadcast(req.venue_id)

    return {"interventions": recommendations, "count": len(recommendations)}


@app.put("/interventions/{intervention_id}")
async def update_intervention(intervention_id: str, action: InterventionAction):
    """Approve or dismiss an intervention."""
    valid_actions = ["approve", "dismiss"]
    if action.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Action must be one of: {valid_actions}")

    status_map = {"approve": "approved", "dismiss": "dismissed"}
    new_status = status_map[action.action]

    success = firestore_svc.update_intervention_status(
        intervention_id=intervention_id,
        new_status=new_status,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Intervention not found")

    # If approved, auto-send notification if one exists
    intervention = firestore_svc.get_intervention(intervention_id)
    if intervention and action.action == "approve" and "notification" in intervention:
        notif = intervention["notification"]
        notification_svc.send_to_zones({
            "title": notif.get("title", ""),
            "body": notif.get("body", ""),
            "type": notif.get("type", "general"),
            "target_zones": [intervention.get("target_zone", "")],
            "venue_id": intervention.get("venue_id", "stadium_01"),
        })

    trigger_broadcast("stadium_01")

    return {
        "intervention_id": intervention_id,
        "status": new_status,
        "action": action.action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/notify")
async def send_notification(req: NotifyRequest, background_tasks: BackgroundTasks):
    """Send push notification to fans in target zones."""
    notification_id = str(uuid.uuid4())

    payload = {
        "notification_id": notification_id,
        "venue_id": req.venue_id,
        "target_zones": req.target_zones,
        "title": req.title,
        "body": req.body,
        "type": req.notification_type,
        "priority": req.priority,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }

    # Store notification
    firestore_svc.create_notification(notification_id, payload)

    # Send via FCM in background
    background_tasks.add_task(notification_svc.send_to_zones, payload)
    background_tasks.add_task(pubsub_svc.publish, "user_notifications", payload)

    # Push to fan WebSocket clients
    await ws_manager.broadcast("fan", {
        "type": "notification",
        "title": req.title,
        "body": req.body,
        "notification_type": req.notification_type,
        "priority": req.priority,
    })

    return {"notification_id": notification_id, "status": "sent"}


# ---------------------------------------------------------------------------
# Simulation Endpoints (Demo Mode)
# ---------------------------------------------------------------------------

@app.post("/simulation/start")
async def start_simulation(req: SimulationStartRequest):
    """Start the synthetic event simulation for demo mode."""
    if simulation_engine._running:
        return {"status": "already_running", "phase": simulation_engine._phase}

    # Run simulation in a separate thread (not BackgroundTasks)
    sim_thread = threading.Thread(
        target=simulation_engine.run,
        kwargs={
            "mode": req.mode,
            "speed_factor": req.speed_factor,
            "venue_id": req.venue_id,
        },
        daemon=True,
    )
    sim_thread.start()

    return {
        "status": "simulation_started",
        "mode": req.mode,
        "speed_factor": req.speed_factor,
        "venue_id": req.venue_id,
    }


@app.post("/simulation/stop")
async def stop_simulation():
    """Stop the running simulation."""
    simulation_engine.stop()
    return {"status": "simulation_stopped"}


@app.get("/simulation/status")
async def simulation_status():
    """Get current simulation status."""
    return simulation_engine.get_status()


# ---------------------------------------------------------------------------
# State Query Endpoints (for frontend)
# ---------------------------------------------------------------------------

@app.get("/state/{venue_id}")
async def get_venue_state(venue_id: str):
    """Get current venue state (all zones, gates, concessions)."""
    return firestore_svc.get_venue_state(venue_id)


@app.get("/state/{venue_id}/zones")
async def get_zones(venue_id: str):
    """Get all zone states for a venue."""
    return firestore_svc.get_zones(venue_id)


@app.get("/state/{venue_id}/queues")
async def get_queues(venue_id: str):
    """Get all queue states (gates, concessions, restrooms)."""
    return firestore_svc.get_queues(venue_id)


@app.get("/interventions/{venue_id}")
async def get_interventions(venue_id: str, status: Optional[str] = None):
    """Get interventions for a venue, optionally filtered by status."""
    return firestore_svc.get_interventions(venue_id, status_filter=status)


@app.get("/kpis/{venue_id}")
async def get_kpis(venue_id: str):
    """Get current KPI metrics for before/after comparison."""
    return firestore_svc.get_kpis(venue_id)


# ---------------------------------------------------------------------------
# Fan-facing endpoints
# ---------------------------------------------------------------------------

@app.get("/fan/{venue_id}/best-gate")
async def best_gate(venue_id: str, section: Optional[str] = None):
    """Recommend the best gate for a fan to use right now."""
    queues = firestore_svc.get_queues(venue_id)
    gates = {k: v for k, v in queues.items() if v.get("point_type") == "gate"}
    if not gates:
        return {"recommendation": "No gate data available yet"}

    # Section-aware: prioritize gates near the fan's section
    if section:
        section_gate_map = {
            "A1": "gate_A", "A2": "gate_A",
            "B1": "gate_B", "B2": "gate_B",
            "C1": "gate_C", "C2": "gate_C",
            "D1": "gate_D", "D2": "gate_D",
        }
        nearby_gate = section_gate_map.get(section.replace("zone_", ""))
        if nearby_gate and nearby_gate in gates:
            nearby_wait = gates[nearby_gate].get("avgWaitMinutes", 999)
            best = min(gates.items(), key=lambda x: x[1].get("avgWaitMinutes", 999))
            best_wait = best[1].get("avgWaitMinutes", 999)
            # Recommend nearby gate if within 3 min of best
            if nearby_wait <= best_wait + 3:
                return {
                    "best_gate": nearby_gate,
                    "wait_minutes": nearby_wait,
                    "personalized": True,
                    "reason": f"Closest to your section ({section})",
                    "all_gates": gates,
                }

    best = min(gates.items(), key=lambda x: x[1].get("avgWaitMinutes", 999))
    return {
        "best_gate": best[0],
        "wait_minutes": best[1].get("avgWaitMinutes", 0),
        "all_gates": gates,
    }


@app.get("/fan/{venue_id}/best-concession")
async def best_concession(venue_id: str, section: Optional[str] = None):
    """Recommend the best concession stand for a fan."""
    queues = firestore_svc.get_queues(venue_id)
    concessions = {k: v for k, v in queues.items() if v.get("point_type") == "concession"}
    if not concessions:
        return {"recommendation": "No concession data available yet"}
    best = min(concessions.items(), key=lambda x: x[1].get("avgWaitMinutes", 999))
    return {
        "best_concession": best[0],
        "wait_minutes": best[1].get("avgWaitMinutes", 0),
        "all_concessions": concessions,
    }


@app.get("/fan/{venue_id}/exit-guidance")
async def exit_guidance(venue_id: str, section: Optional[str] = None):
    """Get exit guidance based on current congestion."""
    zones = firestore_svc.get_zones(venue_id)
    queues = firestore_svc.get_queues(venue_id)

    gates = {k: v for k, v in queues.items() if v.get("point_type") == "gate"}
    best_exit = min(gates.items(), key=lambda x: x[1].get("congestionScore", 999)) if gates else None

    return {
        "best_exit": best_exit[0] if best_exit else "gate_A",
        "congestion_score": best_exit[1].get("congestionScore", 0) if best_exit else 0,
        "status": best_exit[1].get("status", "green") if best_exit else "green",
        "message": f"Exit via {best_exit[0].replace('_', ' ').title()} — currently clear" if best_exit else "All exits are clear",
        "all_exits": gates,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
