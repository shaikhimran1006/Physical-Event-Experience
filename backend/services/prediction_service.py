"""
Prediction Service — Queue and crowd prediction using EWMA.
Fast baseline model suitable for hackathon demo.
"""

import math
from typing import Optional


class PredictionService:
    """Exponential Weighted Moving Average (EWMA) prediction engine."""

    # Phase-aware momentum factors
    MOMENTUM = {
        "pre_game": 1.5,
        "in_game": 0.3,
        "halftime": 2.0,
        "post_game": 1.8,
    }

    ALPHA = 0.3  # EWMA smoothing factor

    def __init__(self):
        # Store EWMA state per point
        self._ewma_state: dict[str, float] = {}
        self._history: dict[str, list[float]] = {}

    def predict_queue(
        self,
        point_id: str,
        current_queue_length: int,
        avg_wait_seconds: float = 0,
        throughput_per_min: float = 10.0,
        event_phase: str = "pre_game",
    ) -> dict:
        """
        Predict queue length and wait time for the next 5, 10, and 15 minutes.
        Uses EWMA with phase-aware momentum.
        """
        # Update history
        if point_id not in self._history:
            self._history[point_id] = []
        self._history[point_id].append(current_queue_length)
        if len(self._history[point_id]) > 30:
            self._history[point_id] = self._history[point_id][-30:]

        # Compute rate of change (people per minute)
        history = self._history[point_id]
        if len(history) >= 2:
            # Each entry is ~30s apart in our system
            delta_recent = history[-1] - history[-2]
            rate_of_change = delta_recent * 2  # per minute (2 entries per min)
        else:
            rate_of_change = 0

        # 5-minute delta
        if len(history) >= 10:
            delta_5m = history[-1] - history[-10]
        else:
            delta_5m = rate_of_change * 5

        # EWMA calculation
        prev_ewma = self._ewma_state.get(point_id, current_queue_length)
        ewma = self.ALPHA * current_queue_length + (1 - self.ALPHA) * prev_ewma
        self._ewma_state[point_id] = ewma

        momentum = self.MOMENTUM.get(event_phase, 1.0)

        # Multi-horizon predictions
        pred_5m = max(0, ewma + (rate_of_change * 5 * momentum))
        pred_10m = max(0, ewma + (rate_of_change * 10 * momentum))
        pred_15m = max(0, ewma + (rate_of_change * 15 * momentum))

        # Wait time predictions (queue_length / throughput)
        tp = max(1, throughput_per_min)
        wait_5m = (pred_5m / tp) * 60   # seconds
        wait_10m = (pred_10m / tp) * 60
        wait_15m = (pred_15m / tp) * 60

        # Congestion score
        congestion = self.congestion_score_static(
            current_queue_length, 500, rate_of_change, avg_wait_seconds / 60
        )

        # Trend
        if rate_of_change > 5:
            trend = "increasing_fast"
        elif rate_of_change > 1:
            trend = "increasing"
        elif rate_of_change < -5:
            trend = "decreasing_fast"
        elif rate_of_change < -1:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "point_id": point_id,
            "current_queue_length": current_queue_length,
            "current_wait_seconds": avg_wait_seconds,
            "predictions": {
                "5min": {
                    "queue_length": round(pred_5m),
                    "wait_seconds": round(wait_5m),
                    "wait_minutes": round(wait_5m / 60, 1),
                },
                "10min": {
                    "queue_length": round(pred_10m),
                    "wait_seconds": round(wait_10m),
                    "wait_minutes": round(wait_10m / 60, 1),
                },
                "15min": {
                    "queue_length": round(pred_15m),
                    "wait_seconds": round(wait_15m),
                    "wait_minutes": round(wait_15m / 60, 1),
                },
            },
            "rate_of_change": round(rate_of_change, 1),
            "trend": trend,
            "congestion_score": congestion,
            "event_phase": event_phase,
            "model_version": "ewma_v1",
        }

    @staticmethod
    def congestion_score_static(
        occupancy: int,
        capacity: int,
        rate_of_change: float = 0,
        wait_minutes: float = 0,
    ) -> float:
        """
        Compute congestion score from 0.0 (empty) to 1.0 (critical).
        
        Components:
        - 50% weight: utilization (occupancy / capacity)
        - 30% weight: growth pressure (positive rate of change)
        - 20% weight: wait pressure (wait time / 30 min max)
        """
        if capacity <= 0:
            return 0.0

        utilization = min(1.0, occupancy / capacity)
        growth_pressure = min(1.0, max(0, rate_of_change) / 50)
        wait_pressure = min(1.0, wait_minutes / 30)

        score = (0.5 * utilization) + (0.3 * growth_pressure) + (0.2 * wait_pressure)
        return round(min(1.0, max(0.0, score)), 3)

    @staticmethod
    def simple_predict(current: int, delta_5m: float, phase: str) -> float:
        """Fallback: dead simple linear extrapolation with phase multiplier."""
        multiplier = {"pre_game": 1.5, "in_game": 0.3, "halftime": 2.0, "post_game": 1.8}
        return max(0, current + (delta_5m / 5) * 15 * multiplier.get(phase, 1.0))
