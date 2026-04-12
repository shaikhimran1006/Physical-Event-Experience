import asyncio
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks, HTTPException

from app.core.cache import ReadCache
from app.core.config import get_read_cache_ttl_seconds
from app.schemas.api import (
    CrowdEvent,
    InterventionAction,
    InterventionRequest,
    NotifyRequest,
    QueuePredictionRequest,
    SimulationStartRequest,
)
from app.websocket import ConnectionManager
from services.bigquery_service import BigQueryService
from services.firestore_service import FirestoreService
from services.notification_service import NotificationService
from services.prediction_service import PredictionService
from services.pubsub_service import PubSubService
from services.recommendation_service import RecommendationService
from simulation.event_generator import SimulationEngine

logger = logging.getLogger("stadium.os.api")


class PlatformService:
    def __init__(self):
        self.requested_use_gcp = os.getenv("USE_GCP", "false").lower() == "true"
        self.topics = {
            "crowd": os.getenv("PUBSUB_CROWD_TOPIC", "crowd_events"),
            "queue": os.getenv("PUBSUB_QUEUE_TOPIC", "queue_events"),
            "interventions": os.getenv("PUBSUB_INTERVENTIONS_TOPIC", "interventions"),
            "notifications": os.getenv("PUBSUB_NOTIFICATIONS_TOPIC", "user_notifications"),
        }

        self.firestore_svc = FirestoreService(use_gcp=self.requested_use_gcp)
        self.pubsub_svc = PubSubService(use_gcp=self.requested_use_gcp)
        self.bq_svc = BigQueryService(use_gcp=self.requested_use_gcp)
        self.prediction_svc = PredictionService()
        self.recommendation_svc = RecommendationService()
        self.notification_svc = NotificationService(use_gcp=self.requested_use_gcp)
        self.simulation_engine = SimulationEngine(
            self.firestore_svc,
            self.prediction_svc,
            self.recommendation_svc,
            self.notification_svc,
        )

        self.service_gcp_modes = {
            "firestore": self.firestore_svc.use_gcp,
            "pubsub": self.pubsub_svc.use_gcp,
            "bigquery": self.bq_svc.use_gcp,
            "notification": self.notification_svc.use_gcp,
        }
        self.active_use_gcp = any(self.service_gcp_modes.values())

        self.ws_manager = ConnectionManager()
        self.read_cache = ReadCache(ttl_seconds=get_read_cache_ttl_seconds())
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.ready = False

        self.simulation_engine.set_broadcast_callback(self.trigger_broadcast)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = loop

    def mark_ready(self, is_ready: bool) -> None:
        self.ready = is_ready

    def invalidate_cache(self) -> None:
        self.read_cache.invalidate()

    def get_or_set_cache(self, cache_key: str, compute_fn):
        return self.read_cache.get_or_set(cache_key, compute_fn)

    async def broadcast_venue_state(self, venue_id: str):
        try:
            state = self.firestore_svc.get_venue_state(venue_id)
            kpis = self.firestore_svc.get_kpis(venue_id)
            interventions = self.firestore_svc.get_interventions(venue_id)
            sim_status = self.simulation_engine.get_status()

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
            await self.ws_manager.broadcast("dashboard", dashboard_msg)

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
                }
                if best_gate_id
                else None,
                "best_concession": {
                    "best_concession": best_conc_id,
                    "wait_minutes": concessions[best_conc_id].get("avgWaitMinutes", 0) if best_conc_id else 0,
                    "all_concessions": concessions,
                }
                if best_conc_id
                else None,
                "simulation": sim_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.ws_manager.broadcast("fan", fan_msg)
        except Exception as exc:
            logger.error("WebSocket broadcast error: %s", exc)

    def trigger_broadcast(self, venue_id: str = "stadium_01"):
        if self._event_loop and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_venue_state(venue_id), self._event_loop)

    def health_payload(self, security_payload: dict) -> dict:
        return {
            "status": "healthy",
            "service": "Stadium OS Copilot API",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gcp_requested": self.requested_use_gcp,
            "gcp_enabled": self.active_use_gcp,
            "gcp_services": self.service_gcp_modes,
            "security": security_payload,
            "websocket_connections": {
                key: len(value) for key, value in self.ws_manager.active_connections.items()
            },
            "liveness": "alive",
            "readiness": "ready" if self.ready else "not_ready",
        }

    def readiness_payload(self) -> dict:
        dependencies = {
            "firestore": self.firestore_svc is not None,
            "pubsub": self.pubsub_svc is not None,
            "bigquery": self.bq_svc is not None,
            "prediction": self.prediction_svc is not None,
            "recommendation": self.recommendation_svc is not None,
            "notification": self.notification_svc is not None,
            "simulation": self.simulation_engine is not None,
            "event_loop": self._event_loop is not None,
        }
        ready = self.ready and all(dependencies.values())
        return {
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": dependencies,
        }

    def ingest_crowd_event(self, event: CrowdEvent, background_tasks: BackgroundTasks) -> dict:
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

        self.firestore_svc.update_zone_state(
            venue_id=event.venue_id,
            zone_id=event.zone_id,
            occupancy=event.occupancy_count,
            event_phase=event.event_phase,
        )

        background_tasks.add_task(self.pubsub_svc.publish, self.topics["crowd"], payload)
        background_tasks.add_task(self.bq_svc.insert_crowd_event, payload)

        self.invalidate_cache()
        self.trigger_broadcast(event.venue_id)

        return {"event_id": event_id, "status": "ingested", "timestamp": timestamp}

    def ingest_queue_event(self, event: QueuePredictionRequest, background_tasks: BackgroundTasks) -> dict:
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

        self.firestore_svc.update_queue_state(
            venue_id=event.venue_id,
            point_id=event.point_id,
            point_type=event.point_type,
            queue_length=event.current_queue_length,
            avg_wait_seconds=event.avg_wait_seconds,
            throughput_per_min=event.throughput_per_min,
        )

        background_tasks.add_task(self.pubsub_svc.publish, self.topics["queue"], payload)
        background_tasks.add_task(self.bq_svc.insert_queue_event, payload)

        self.invalidate_cache()
        self.trigger_broadcast(event.venue_id)

        return {"event_id": event_id, "status": "ingested"}

    def predict_queue(self, req: QueuePredictionRequest) -> dict:
        prediction = self.prediction_svc.predict_queue(
            point_id=req.point_id,
            current_queue_length=req.current_queue_length,
            avg_wait_seconds=req.avg_wait_seconds,
            throughput_per_min=req.throughput_per_min,
            event_phase=req.event_phase,
        )

        self.firestore_svc.update_prediction(
            venue_id=req.venue_id,
            point_id=req.point_id,
            point_type=req.point_type,
            prediction=prediction,
        )

        self.invalidate_cache()
        return prediction

    def recommend_intervention(self, req: InterventionRequest, background_tasks: BackgroundTasks) -> dict:
        current_state = self.firestore_svc.get_venue_state(req.venue_id)

        recommendations = self.recommendation_svc.generate_interventions(
            venue_id=req.venue_id,
            current_state=current_state,
            zone_filter=req.zone_id,
        )

        for rec in recommendations:
            intervention_id = str(uuid.uuid4())
            rec["intervention_id"] = intervention_id
            rec["venue_id"] = req.venue_id
            rec["status"] = "pending"
            rec["created_at"] = datetime.now(timezone.utc).isoformat()
            self.firestore_svc.create_intervention(intervention_id, rec)
            background_tasks.add_task(self.pubsub_svc.publish, self.topics["interventions"], rec)

        self.invalidate_cache()
        self.trigger_broadcast(req.venue_id)

        return {"interventions": recommendations, "count": len(recommendations)}

    def update_intervention(self, intervention_id: str, action: InterventionAction) -> dict:
        status_map = {"approve": "approved", "dismiss": "dismissed"}
        new_status = status_map[action.action]

        success = self.firestore_svc.update_intervention_status(
            intervention_id=intervention_id,
            new_status=new_status,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Intervention not found")

        intervention = self.firestore_svc.get_intervention(intervention_id)
        venue_id = "stadium_01"

        if intervention:
            venue_id = intervention.get("venue_id", "stadium_01")

        if intervention and action.action == "approve" and "notification" in intervention:
            notif = intervention["notification"]
            self.notification_svc.send_to_zones(
                {
                    "title": notif.get("title", ""),
                    "body": notif.get("body", ""),
                    "type": notif.get("type", "general"),
                    "target_zones": [intervention.get("target_zone", "")],
                    "venue_id": venue_id,
                }
            )

        self.invalidate_cache()
        self.trigger_broadcast(venue_id)

        return {
            "intervention_id": intervention_id,
            "status": new_status,
            "action": action.action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def send_notification(self, req: NotifyRequest, background_tasks: BackgroundTasks) -> dict:
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

        self.firestore_svc.create_notification(notification_id, payload)
        background_tasks.add_task(self.notification_svc.send_to_zones, payload)
        background_tasks.add_task(self.pubsub_svc.publish, self.topics["notifications"], payload)

        self.invalidate_cache()

        await self.ws_manager.broadcast(
            "fan",
            {
                "type": "notification",
                "title": req.title,
                "body": req.body,
                "notification_type": req.notification_type,
                "priority": req.priority,
            },
        )

        return {"notification_id": notification_id, "status": "sent"}

    def start_simulation(self, req: SimulationStartRequest) -> dict:
        if self.simulation_engine._running:
            return {"status": "already_running", "phase": self.simulation_engine._phase}

        sim_thread = threading.Thread(
            target=self.simulation_engine.run,
            kwargs={
                "mode": req.mode,
                "speed_factor": req.speed_factor,
                "venue_id": req.venue_id,
            },
            daemon=True,
        )
        sim_thread.start()

        self.invalidate_cache()

        return {
            "status": "simulation_started",
            "mode": req.mode,
            "speed_factor": req.speed_factor,
            "venue_id": req.venue_id,
        }

    def stop_simulation(self) -> dict:
        self.simulation_engine.stop()
        self.invalidate_cache()
        return {"status": "simulation_stopped"}

    def simulation_status(self) -> dict:
        return self.simulation_engine.get_status()

    def get_venue_state(self, venue_id: str) -> dict:
        cache_key = f"state:{venue_id}"
        return self.get_or_set_cache(cache_key, lambda: self.firestore_svc.get_venue_state(venue_id))

    def get_zones(self, venue_id: str) -> dict:
        cache_key = f"zones:{venue_id}"
        return self.get_or_set_cache(cache_key, lambda: self.firestore_svc.get_zones(venue_id))

    def get_queues(self, venue_id: str) -> dict:
        cache_key = f"queues:{venue_id}"
        return self.get_or_set_cache(cache_key, lambda: self.firestore_svc.get_queues(venue_id))

    def get_interventions(self, venue_id: str, status: Optional[str], limit: int, offset: int) -> list[dict]:
        cache_key = f"interventions:{venue_id}:{status}:{limit}:{offset}"

        def _read_interventions():
            all_items = self.firestore_svc.get_interventions(venue_id, status_filter=status)
            return all_items[offset : offset + limit]

        return self.get_or_set_cache(cache_key, _read_interventions)

    def get_kpis(self, venue_id: str) -> dict:
        cache_key = f"kpis:{venue_id}"
        return self.get_or_set_cache(cache_key, lambda: self.firestore_svc.get_kpis(venue_id))

    def best_gate(self, venue_id: str, section: Optional[str] = None) -> dict:
        cache_key = f"fan-best-gate:{venue_id}:{section}"

        def _get_best_gate():
            queues = self.firestore_svc.get_queues(venue_id)
            gates = {k: v for k, v in queues.items() if v.get("point_type") == "gate"}
            if not gates:
                return {"recommendation": "No gate data available yet"}

            if section:
                section_gate_map = {
                    "A1": "gate_A",
                    "A2": "gate_A",
                    "B1": "gate_B",
                    "B2": "gate_B",
                    "C1": "gate_C",
                    "C2": "gate_C",
                    "D1": "gate_D",
                    "D2": "gate_D",
                }
                nearby_gate = section_gate_map.get(section.replace("zone_", ""))
                if nearby_gate and nearby_gate in gates:
                    nearby_wait = gates[nearby_gate].get("avgWaitMinutes", 999)
                    best = min(gates.items(), key=lambda x: x[1].get("avgWaitMinutes", 999))
                    best_wait = best[1].get("avgWaitMinutes", 999)
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

        return self.get_or_set_cache(cache_key, _get_best_gate)

    def best_concession(self, venue_id: str, section: Optional[str] = None) -> dict:
        cache_key = f"fan-best-concession:{venue_id}:{section}"

        def _get_best_concession():
            queues = self.firestore_svc.get_queues(venue_id)
            concessions = {k: v for k, v in queues.items() if v.get("point_type") == "concession"}
            if not concessions:
                return {"recommendation": "No concession data available yet"}
            best = min(concessions.items(), key=lambda x: x[1].get("avgWaitMinutes", 999))
            return {
                "best_concession": best[0],
                "wait_minutes": best[1].get("avgWaitMinutes", 0),
                "all_concessions": concessions,
            }

        return self.get_or_set_cache(cache_key, _get_best_concession)

    def exit_guidance(self, venue_id: str, section: Optional[str] = None) -> dict:
        cache_key = f"fan-exit:{venue_id}:{section}"

        def _get_exit_guidance():
            queues = self.firestore_svc.get_queues(venue_id)
            gates = {k: v for k, v in queues.items() if v.get("point_type") == "gate"}
            best_exit = min(gates.items(), key=lambda x: x[1].get("congestionScore", 999)) if gates else None

            return {
                "best_exit": best_exit[0] if best_exit else "gate_A",
                "congestion_score": best_exit[1].get("congestionScore", 0) if best_exit else 0,
                "status": best_exit[1].get("status", "green") if best_exit else "green",
                "message": f"Exit via {best_exit[0].replace('_', ' ').title()} — currently clear" if best_exit else "All exits are clear",
                "all_exits": gates,
            }

        return self.get_or_set_cache(cache_key, _get_exit_guidance)
