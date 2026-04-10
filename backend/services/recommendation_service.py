"""
Recommendation Service — Intervention generation with anti-herding logic.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional


class RecommendationService:
    """Generate smart interventions and recommendations."""

    # Congestion thresholds
    YELLOW_THRESHOLD = 0.3
    ORANGE_THRESHOLD = 0.6
    RED_THRESHOLD = 0.8

    # Anti-herding: max % of overflow to redirect to single alternative
    MAX_REDIRECT_PCT = 0.3

    def generate_interventions(
        self,
        venue_id: str,
        current_state: dict,
        zone_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Analyze current state and generate intervention recommendations.
        Implements anti-herding: distributes redirections across alternatives.
        """
        interventions = []
        zones = current_state.get("zones", {})
        queues = current_state.get("queues", {})

        # Evaluate zones for crowd interventions
        for zone_id, zone_data in zones.items():
            if zone_filter and zone_id != zone_filter:
                continue

            congestion = zone_data.get("congestionScore", 0)
            status = zone_data.get("status", "green")

            if congestion >= self.RED_THRESHOLD:
                intervention = self._generate_zone_intervention(
                    zone_id, zone_data, zones, "critical"
                )
                if intervention:
                    interventions.append(intervention)
            elif congestion >= self.ORANGE_THRESHOLD:
                intervention = self._generate_zone_intervention(
                    zone_id, zone_data, zones, "high"
                )
                if intervention:
                    interventions.append(intervention)

        # Evaluate queues for queue interventions
        for point_id, queue_data in queues.items():
            congestion = queue_data.get("congestionScore", 0)
            point_type = queue_data.get("point_type", "gate")

            if congestion >= self.RED_THRESHOLD:
                intervention = self._generate_queue_intervention(
                    point_id, queue_data, queues, "critical"
                )
                if intervention:
                    interventions.append(intervention)
            elif congestion >= self.ORANGE_THRESHOLD:
                intervention = self._generate_queue_intervention(
                    point_id, queue_data, queues, "high"
                )
                if intervention:
                    interventions.append(intervention)

        return interventions

    def _generate_zone_intervention(
        self, zone_id: str, zone_data: dict, all_zones: dict, severity: str
    ) -> Optional[dict]:
        """Generate a zone-level intervention (crowd redistribution)."""
        # Find the best alternative zones (anti-herding: spread across multiple)
        alternatives = self._find_alternatives(
            zone_id, zone_data, all_zones, max_redirect_pct=self.MAX_REDIRECT_PCT
        )

        if not alternatives:
            # No alternatives — suggest staff deployment instead
            return {
                "type": "staff_deploy",
                "target_zone": zone_id,
                "severity": severity,
                "recommendation": (
                    f"Deploy additional staff to {zone_id.replace('_', ' ').upper()} — "
                    f"congestion at {zone_data.get('congestionScore', 0):.0%}"
                ),
                "details": {
                    "current_occupancy": zone_data.get("currentOccupancy", 0),
                    "congestion_score": zone_data.get("congestionScore", 0),
                },
            }

        alt_text = ", ".join(
            [f"{a['target'].replace('_', ' ').upper()} ({a['congestion']:.0%} full)"
             for a in alternatives[:3]]
        )

        return {
            "type": "reroute",
            "target_zone": zone_id,
            "severity": severity,
            "recommendation": (
                f"Redirect from {zone_id.replace('_', ' ').upper()} to: {alt_text}"
            ),
            "alternatives": alternatives,
            "details": {
                "current_occupancy": zone_data.get("currentOccupancy", 0),
                "congestion_score": zone_data.get("congestionScore", 0),
            },
        }

    def _generate_queue_intervention(
        self, point_id: str, queue_data: dict, all_queues: dict, severity: str
    ) -> Optional[dict]:
        """Generate a queue-level intervention."""
        point_type = queue_data.get("point_type", "gate")
        same_type_queues = {
            k: v for k, v in all_queues.items()
            if v.get("point_type") == point_type and k != point_id
        }

        alternatives = self._find_alternatives(
            point_id, queue_data, same_type_queues, self.MAX_REDIRECT_PCT
        )

        wait_min = queue_data.get("avgWaitMinutes", 0)
        pred = queue_data.get("prediction", {})
        pred_wait = pred.get("15min", {}).get("wait_minutes", wait_min) if isinstance(pred, dict) else wait_min

        type_label = point_type.replace("_", " ").title()

        if alternatives:
            best_alt = alternatives[0]
            savings = round(wait_min - best_alt.get("wait_minutes", wait_min), 1)

            alt_labels = ", ".join(
                [f"{a['target'].replace('_', ' ').title()} ({a.get('wait_minutes', '?')} min)"
                 for a in alternatives[:3]]
            )

            return {
                "type": "reroute",
                "target_zone": point_id,
                "severity": severity,
                "recommendation": (
                    f"{point_id.replace('_', ' ').title()} has {wait_min:.0f} min wait "
                    f"(predicted {pred_wait:.0f} min in 15 min). "
                    f"Suggest: {alt_labels}. Save ~{max(0, savings):.0f} min."
                ),
                "alternatives": alternatives,
                "notification": {
                    "title": f"Skip the wait at {type_label}!",
                    "body": (
                        f"{alternatives[0]['target'].replace('_', ' ').title()} has only "
                        f"{alternatives[0].get('wait_minutes', '?')} min wait — "
                        f"save {max(0, savings):.0f} min"
                    ),
                    "type": "queue_alert",
                },
                "details": {
                    "point_type": point_type,
                    "current_wait": wait_min,
                    "predicted_wait_15m": pred_wait,
                    "congestion_score": queue_data.get("congestionScore", 0),
                },
            }
        else:
            return {
                "type": "alert",
                "target_zone": point_id,
                "severity": severity,
                "recommendation": (
                    f"{point_id.replace('_', ' ').title()} at {queue_data.get('congestionScore', 0):.0%} "
                    f"capacity — no better alternatives. Deploy additional staff."
                ),
                "details": {
                    "point_type": point_type,
                    "current_wait": wait_min,
                    "congestion_score": queue_data.get("congestionScore", 0),
                },
            }

    def _find_alternatives(
        self, source_id: str, source_data: dict, all_items: dict,
        max_redirect_pct: float = 0.3
    ) -> list[dict]:
        """
        Find best alternatives with anti-herding logic.
        Distributes overflow across multiple targets (max 30% each).
        """
        source_congestion = source_data.get("congestionScore", 0)
        wait_min = source_data.get("avgWaitMinutes", 0)

        candidates = []
        for item_id, item_data in all_items.items():
            if item_id == source_id:
                continue
            item_congestion = item_data.get("congestionScore", 0)
            # Only recommend if significantly less congested
            if item_congestion < source_congestion * 0.7:
                candidates.append({
                    "target": item_id,
                    "congestion": item_congestion,
                    "wait_minutes": item_data.get("avgWaitMinutes", 0),
                    "status": item_data.get("status", "green"),
                    "redirect_pct": min(max_redirect_pct, 1.0 - item_congestion),
                })

        # Sort by congestion (lowest first)
        candidates.sort(key=lambda x: x["congestion"])
        return candidates[:5]  # Top 5 alternatives max
