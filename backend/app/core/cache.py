import copy
import threading
from time import monotonic
from typing import Any, Callable


class ReadCache:
    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, Any]] = {}

    def invalidate(self) -> None:
        with self._lock:
            self._data.clear()

    def get(self, key: str) -> Any | None:
        now = monotonic()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return copy.deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        expires_at = monotonic() + self.ttl_seconds
        with self._lock:
            self._data[key] = (expires_at, copy.deepcopy(value))

    def get_or_set(self, key: str, compute_fn: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute_fn()
        self.set(key, value)
        return value
