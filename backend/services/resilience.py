import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, TypeVar

logger = logging.getLogger("stadium.os.resilience")

T = TypeVar("T")


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int
    recovery_timeout_sec: float

    def __post_init__(self):
        self._state = "closed"
        self._failure_count = 0
        self._last_failure_ts = 0.0

    def _can_attempt(self) -> bool:
        if self._state != "open":
            return True
        if (time.monotonic() - self._last_failure_ts) >= self.recovery_timeout_sec:
            self._state = "half-open"
            return True
        return False

    def _mark_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def _mark_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_ts = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"

    def call(self, fn: Callable[[], T]) -> T:
        if not self._can_attempt():
            raise RuntimeError(f"Circuit open for {self.name}")

        try:
            result = fn()
        except Exception:
            self._mark_failure()
            raise

        self._mark_success()
        return result


def _default_retry_attempts() -> int:
    raw = os.getenv("GCP_RETRY_MAX_ATTEMPTS", "3").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 3
    return max(1, parsed)


def retry_with_backoff(
    operation: Callable[[], T],
    operation_name: str,
    max_attempts: int | None = None,
    base_delay_sec: float = 0.2,
    max_delay_sec: float = 2.0,
) -> T:
    attempts = max_attempts if max_attempts is not None else _default_retry_attempts()
    delay = base_delay_sec
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            payload = {
                "event": "retry_attempt_failed",
                "operation": operation_name,
                "attempt": attempt,
                "max_attempts": attempts,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.warning(json.dumps(payload, separators=(",", ":")))

            if attempt >= attempts:
                break

            time.sleep(delay)
            delay = min(max_delay_sec, delay * 2)

    raise RuntimeError(f"Operation failed after {attempts} attempts: {operation_name}") from last_error
