from services.prediction_service import PredictionService


def test_predict_queue_returns_all_horizons():
    svc = PredictionService()

    first = svc.predict_queue(
        point_id="gate_A",
        current_queue_length=15,
        avg_wait_seconds=90,
        throughput_per_min=10,
        event_phase="pre_game",
    )
    second = svc.predict_queue(
        point_id="gate_A",
        current_queue_length=24,
        avg_wait_seconds=120,
        throughput_per_min=10,
        event_phase="pre_game",
    )

    assert first["point_id"] == "gate_A"
    assert set(second["predictions"].keys()) == {"5min", "10min", "15min"}
    assert second["predictions"]["5min"]["wait_seconds"] >= 0
    assert second["trend"] in {
        "increasing_fast",
        "increasing",
        "stable",
        "decreasing",
        "decreasing_fast",
    }


def test_congestion_score_stays_bounded():
    score = PredictionService.congestion_score_static(
        occupancy=600,
        capacity=500,
        rate_of_change=40,
        wait_minutes=50,
    )
    assert 0.0 <= score <= 1.0
