"""
Firestore Service — Real-time state management.
Supports both GCP Firestore and local in-memory fallback for demo/dev.
"""

import os
import threading
import logging
from datetime import datetime, timezone
from typing import Optional


logger = logging.getLogger(__name__)


class FirestoreService:
    def __init__(self, use_gcp: bool = False):
        self.use_gcp = use_gcp
        self._lock = threading.Lock()
        self.db = None

        if use_gcp:
            try:
                from google.cloud import firestore
                self.db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
            except Exception as exc:
                logger.warning(
                    "Firestore initialization failed; falling back to local in-memory mode. "
                    "Set USE_GCP=false for local runs or configure ADC/service account for GCP. Error: %s",
                    exc,
                )
                self.use_gcp = False

        if not self.use_gcp:
            # In-memory store for local dev / demo
            self._store = {
                "zones": {},
                "queues": {},
                "interventions": {},
                "notifications": {},
                "kpis": {},
            }

    # ── Zone State ──────────────────────────────────────────────────────

    def update_zone_state(self, venue_id: str, zone_id: str, occupancy: int,
                          event_phase: str = "pre_game", capacity: int = 5000):
        """Update real-time zone occupancy."""
        from services.prediction_service import PredictionService

        congestion = PredictionService.congestion_score_static(
            occupancy, capacity, 0, 0
        )
        status = "green"
        if congestion >= 0.8:
            status = "red"
        elif congestion >= 0.6:
            status = "orange"
        elif congestion >= 0.3:
            status = "yellow"

        data = {
            "zone_id": zone_id,
            "currentOccupancy": occupancy,
            "capacity": capacity,
            "congestionScore": congestion,
            "status": status,
            "eventPhase": event_phase,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        if self.use_gcp:
            self.db.collection("current_state").document(venue_id)\
                .collection("zones").document(zone_id).set(data, merge=True)
        else:
            with self._lock:
                self._store["zones"][zone_id] = data

    # ── Queue State ─────────────────────────────────────────────────────

    def update_queue_state(self, venue_id: str, point_id: str, point_type: str,
                           queue_length: int, avg_wait_seconds: float,
                           throughput_per_min: float, capacity: int = 500):
        """Update real-time queue state for gates/concessions/restrooms."""
        from services.prediction_service import PredictionService

        avg_wait_minutes = avg_wait_seconds / 60
        congestion = PredictionService.congestion_score_static(
            queue_length, capacity, 0, avg_wait_minutes
        )
        status = "green"
        if congestion >= 0.8:
            status = "red"
        elif congestion >= 0.6:
            status = "orange"
        elif congestion >= 0.3:
            status = "yellow"

        data = {
            "point_id": point_id,
            "point_type": point_type,
            "currentQueueLength": queue_length,
            "avgWaitMinutes": round(avg_wait_minutes, 1),
            "avgWaitSeconds": avg_wait_seconds,
            "throughputPerMin": throughput_per_min,
            "capacity": capacity,
            "congestionScore": round(congestion, 3),
            "status": status,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        if self.use_gcp:
            self.db.collection("current_state").document(venue_id)\
                .collection("queues").document(point_id).set(data, merge=True)
        else:
            with self._lock:
                self._store["queues"][point_id] = data

    # ── Predictions ─────────────────────────────────────────────────────

    def update_prediction(self, venue_id: str, point_id: str, point_type: str,
                          prediction: dict):
        """Update prediction data for a queue point."""
        if self.use_gcp:
            self.db.collection("current_state").document(venue_id)\
                .collection("queues").document(point_id).set(
                    {"prediction": prediction}, merge=True
                )
        else:
            with self._lock:
                if point_id in self._store["queues"]:
                    self._store["queues"][point_id]["prediction"] = prediction

    # ── Interventions ────────────────────────────────────────────────────

    def create_intervention(self, intervention_id: str, data: dict):
        """Create a new intervention record."""
        if self.use_gcp:
            self.db.collection("interventions").document(intervention_id).set(data)
        else:
            with self._lock:
                self._store["interventions"][intervention_id] = data

    def get_intervention(self, intervention_id: str) -> Optional[dict]:
        """Get a single intervention by ID."""
        if self.use_gcp:
            doc = self.db.collection("interventions").document(intervention_id).get()
            return doc.to_dict() if doc.exists else None
        else:
            with self._lock:
                return self._store["interventions"].get(intervention_id)

    def update_intervention_status(self, intervention_id: str, new_status: str) -> bool:
        """Update the status of an intervention (approve/dismiss)."""
        if self.use_gcp:
            doc_ref = self.db.collection("interventions").document(intervention_id)
            doc = doc_ref.get()
            if not doc.exists:
                return False
            doc_ref.update({"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()})
            return True
        else:
            with self._lock:
                if intervention_id in self._store["interventions"]:
                    self._store["interventions"][intervention_id]["status"] = new_status
                    self._store["interventions"][intervention_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
                    return True
                return False

    def get_interventions(self, venue_id: str, status_filter: Optional[str] = None):
        """Get interventions, optionally filtered by status."""
        if self.use_gcp:
            query = self.db.collection("interventions")\
                .where("venue_id", "==", venue_id)
            if status_filter:
                query = query.where("status", "==", status_filter)
            docs = query.order_by("created_at", direction="DESCENDING").limit(50).stream()
            return [doc.to_dict() for doc in docs]
        else:
            with self._lock:
                items = list(self._store["interventions"].values())
                items = [i for i in items if i.get("venue_id") == venue_id]
                if status_filter:
                    items = [i for i in items if i.get("status") == status_filter]
                return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)[:50]

    # ── Notifications ────────────────────────────────────────────────────

    def create_notification(self, notification_id: str, data: dict):
        """Store a notification record."""
        if self.use_gcp:
            self.db.collection("notifications").document(notification_id).set(data)
        else:
            with self._lock:
                self._store["notifications"][notification_id] = data

    # ── State Queries ────────────────────────────────────────────────────

    def get_venue_state(self, venue_id: str) -> dict:
        """Get full venue state."""
        return {
            "venue_id": venue_id,
            "zones": self.get_zones(venue_id),
            "queues": self.get_queues(venue_id),
        }

    def get_zones(self, venue_id: str) -> dict:
        """Get all zone states."""
        if self.use_gcp:
            docs = self.db.collection("current_state").document(venue_id)\
                .collection("zones").stream()
            return {doc.id: doc.to_dict() for doc in docs}
        else:
            with self._lock:
                return dict(self._store["zones"])

    def get_queues(self, venue_id: str) -> dict:
        """Get all queue states."""
        if self.use_gcp:
            docs = self.db.collection("current_state").document(venue_id)\
                .collection("queues").stream()
            return {doc.id: doc.to_dict() for doc in docs}
        else:
            with self._lock:
                return dict(self._store["queues"])

    # ── KPIs ─────────────────────────────────────────────────────────────

    def update_kpis(self, venue_id: str, kpis: dict):
        """Update KPI metrics."""
        if self.use_gcp:
            self.db.collection("kpis").document(venue_id).set(kpis, merge=True)
        else:
            with self._lock:
                self._store["kpis"] = kpis

    def get_kpis(self, venue_id: str) -> dict:
        """Get KPI metrics."""
        if self.use_gcp:
            doc = self.db.collection("kpis").document(venue_id).get()
            return doc.to_dict() if doc.exists else {}
        else:
            with self._lock:
                return dict(self._store.get("kpis", {}))
