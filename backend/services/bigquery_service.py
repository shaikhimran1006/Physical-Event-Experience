"""
BigQuery Service — Analytics data pipeline.
Supports GCP BigQuery or local logging fallback.
"""

import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BigQueryService:
    def __init__(self, use_gcp: bool = False):
        self.use_gcp = use_gcp
        self.project_id = os.getenv("GCP_PROJECT_ID", "stadium-os-copilot")
        self.dataset_id = os.getenv("BQ_DATASET", "stadium_os_analytics")
        self.client = None

        if use_gcp:
            try:
                from google.cloud import bigquery
                self.client = bigquery.Client(project=self.project_id)
            except Exception as exc:
                logger.warning(
                    "BigQuery initialization failed; falling back to local mode. "
                    "Set USE_GCP=false for local runs or configure ADC/service account for GCP. Error: %s",
                    exc,
                )
                self.use_gcp = False

    def _insert_rows(self, table_name: str, rows: list[dict]):
        """Insert rows into a BigQuery table."""
        if self.use_gcp and self.client:
            try:
                table_ref = f"{self.project_id}.{self.dataset_id}.{table_name}"
                errors = self.client.insert_rows_json(table_ref, rows)
                if errors:
                    logger.error(f"BigQuery insert errors: {errors}")
                return errors
            except Exception as exc:
                logger.error(
                    "BigQuery insert failed for table %s; using local fallback. Error: %s",
                    table_name,
                    exc,
                )
        else:
            logger.info(f"[LOCAL BQ] {table_name}: {len(rows)} rows")
            return []

        logger.info(f"[LOCAL BQ] {table_name}: {len(rows)} rows")
        return []

    def insert_crowd_event(self, event: dict):
        """Insert a crowd event into BigQuery."""
        row = {
            "event_id": event["event_id"],
            "venue_id": event["venue_id"],
            "zone_id": event["zone_id"],
            "timestamp": event["timestamp"],
            "occupancy_count": event["occupancy_count"],
            "delta": event["delta"],
            "source": event["source"],
            "event_phase": event.get("event_phase", "unknown"),
        }
        return self._insert_rows("crowd_events", [row])

    def insert_queue_event(self, event: dict):
        """Insert a queue event into BigQuery."""
        row = {
            "event_id": event["event_id"],
            "venue_id": event["venue_id"],
            "point_id": event["point_id"],
            "point_type": event.get("point_type", "gate"),
            "timestamp": event["timestamp"],
            "queue_length": event["queue_length"],
            "avg_wait_seconds": event.get("avg_wait_seconds", 0),
            "throughput_per_min": event.get("throughput_per_min", 0),
        }
        return self._insert_rows("queue_events", [row])

    def insert_intervention(self, intervention: dict):
        """Insert an intervention record into BigQuery."""
        row = {
            "intervention_id": intervention["intervention_id"],
            "venue_id": intervention["venue_id"],
            "type": intervention["type"],
            "target_zone": intervention.get("target_zone", ""),
            "severity": intervention.get("severity", "low"),
            "recommendation": intervention.get("recommendation", ""),
            "status": intervention.get("status", "pending"),
            "created_at": intervention.get("created_at", datetime.now(timezone.utc).isoformat()),
            "resolved_at": intervention.get("resolved_at"),
            "response_time_seconds": intervention.get("response_time_seconds"),
        }
        return self._insert_rows("interventions_log", [row])

    def insert_prediction(self, prediction: dict):
        """Insert a prediction record for accuracy tracking."""
        row = {
            "prediction_id": prediction.get("prediction_id", ""),
            "venue_id": prediction.get("venue_id", ""),
            "target_id": prediction.get("target_id", ""),
            "timestamp": prediction.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "predicted_value": prediction.get("predicted_value", 0),
            "actual_value": prediction.get("actual_value"),
            "model_version": prediction.get("model_version", "ewma_v1"),
            "error_pct": prediction.get("error_pct"),
        }
        return self._insert_rows("predictions_log", [row])
