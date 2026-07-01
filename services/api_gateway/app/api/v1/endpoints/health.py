"""
Health check endpoints.

Provides liveness and readiness probes for Kubernetes/Docker health checks.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from app.core.config import settings
from app.db.session import get_db

router = APIRouter()


@router.get("/live", summary="Liveness Probe")
async def liveness() -> dict:
    """
    Liveness probe endpoint.

    Returns 200 if the application process is running.
    Used by container orchestrators to detect stuck processes.
    """
    return {"status": "alive", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/ready", summary="Readiness Probe")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Readiness probe endpoint.

    Checks database and Redis connectivity before reporting ready.
    Used by orchestrators to route traffic only to healthy instances.
    """
    # Check database
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    redis_status = "healthy"
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception:
        redis_status = "unhealthy"

    overall_status = "ready" if db_status == "healthy" and redis_status == "healthy" else "not_ready"

    return {
        "status": overall_status,
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "checks": {
            "database": db_status,
            "redis": redis_status,
        },
    }


@router.get("/startup", summary="Startup Probe")
async def startup() -> dict:
    """
    Startup probe endpoint.

    Indicates the application has completed initialization.
    """
    return {"status": "started", "service": settings.APP_NAME}