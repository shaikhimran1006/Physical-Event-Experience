import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.cache import ReadCache
from app.core.config import allow_credentials, get_cors_origins
from app.core.observability import register_observability


def test_read_cache_set_get_expire_and_invalidate():
    cache = ReadCache(ttl_seconds=0.02)
    cache.set("k", {"value": 1})

    found = cache.get("k")
    assert found == {"value": 1}

    # Ensure deep-copy behavior keeps cache immutable to callers.
    found["value"] = 2
    assert cache.get("k") == {"value": 1}

    time.sleep(0.06)
    assert cache.get("k") is None

    cache.set("another", {"ok": True})
    cache.invalidate()
    assert cache.get("another") is None


def test_read_cache_get_or_set_reuses_cached_value():
    cache = ReadCache(ttl_seconds=1.0)
    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return {"calls": calls["count"]}

    first = cache.get_or_set("answer", compute)
    second = cache.get_or_set("answer", compute)

    assert first == {"calls": 1}
    assert second == {"calls": 1}
    assert calls["count"] == 1


def test_config_cors_origins_parsing(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    defaults = get_cors_origins()
    assert "http://localhost:5173" in defaults
    assert allow_credentials(defaults) is True

    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValueError):
        get_cors_origins()

    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com/, https://b.example.com/")
    parsed = get_cors_origins()
    assert parsed == ["https://a.example.com", "https://b.example.com"]
    assert allow_credentials(parsed) is True


def test_observability_middleware_and_exception_handlers():
    app = FastAPI()
    register_observability(app)

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @app.get("/http-error")
    async def http_error():
        raise HTTPException(status_code=418, detail="teapot")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    @app.get("/items/{item_id}")
    async def item(item_id: int):
        return {"item_id": item_id}

    client = TestClient(app, raise_server_exceptions=False)

    traceparent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    response = client.get(
        "/ok",
        headers={
            "traceparent": traceparent,
            "X-Request-ID": "request-123",
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"
    assert response.headers["X-Trace-ID"] == "0123456789abcdef0123456789abcdef"
    assert "X-Process-Time-ms" in response.headers

    http_response = client.get("/http-error")
    assert http_response.status_code == 418
    assert http_response.json()["error"] == "http_error"

    validation_response = client.get("/items/not-an-int")
    assert validation_response.status_code == 422
    assert validation_response.json()["error"] == "validation_error"

    runtime_response = client.get("/boom")
    assert runtime_response.status_code == 500
    assert runtime_response.json()["error"] == "internal_server_error"
