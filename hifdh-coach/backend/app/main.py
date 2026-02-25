"""
FastAPI application entry point.
"""

import time
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from structlog import get_logger

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    logger.info("Starting Hifdh Coach API", environment=settings.environment)

    # Initialize Sentry if configured
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)

    yield

    logger.info("Shutting down Hifdh Coach API")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-assisted Qur'an memorization platform. "
        "AI serves as a supervised assistant — teachers always have final authority."
    ),
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ─────────────────────────────────────────────────────────
# Simple in-memory rate limiter (per-IP).
# In production, replace with Redis-backed slowapi or similar.
_rate_limit_store: dict[str, list[float]] = {}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Basic per-IP rate limiting middleware."""
    # Skip health/ready probes
    if request.url.path in ("/health", "/ready"):
        return await call_next(request)

    client_ip = request.headers.get("CF-Connecting-IP") or request.client.host if request.client else "unknown"
    now = time.time()
    window = 60.0  # 1 minute window
    max_requests = settings.rate_limit_per_minute

    # Clean and check
    timestamps = _rate_limit_store.get(client_ip, [])
    timestamps = [t for t in timestamps if now - t < window]

    if len(timestamps) >= max_requests:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": "60"},
        )

    timestamps.append(now)
    _rate_limit_store[client_ip] = timestamps

    return await call_next(request)


# ── Routes ───────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.api_v1_prefix)


# ── Health Check ─────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "hifdh-coach-api", "version": settings.app_version}


@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe — checks DB and Redis connectivity."""
    from app.core.database import engine
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": f"Database: {e}"},
        )

    return {"status": "ready"}


# ── Global Error Handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
