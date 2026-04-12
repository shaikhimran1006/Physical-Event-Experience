import os

LOCAL_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]


def get_cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ORIGINS", "").strip()
    if not raw_origins:
        return LOCAL_CORS_ORIGINS
    if raw_origins == "*":
        raise ValueError("Wildcard CORS_ORIGINS is not allowed")

    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    if not origins:
        raise ValueError("CORS_ORIGINS cannot be empty")
    if any(origin == "*" for origin in origins):
        raise ValueError("Wildcard CORS origins are not allowed")

    return origins


def allow_credentials(origins: list[str]) -> bool:
    return True


def get_read_cache_ttl_seconds() -> float:
    return max(0.1, float(os.getenv("READ_CACHE_TTL_SECONDS", "1.0")))
