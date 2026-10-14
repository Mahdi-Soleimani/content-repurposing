"""Health check endpoints."""

from fastapi import APIRouter
import redis.asyncio as aioredis
from sqlalchemy import text

from app.config import settings
from app.database import async_session_maker

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Comprehensive health check for all dependencies."""
    checks = {}

    # Check PostgreSQL
    try:
        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            checks["postgres"] = "healthy"
    except Exception as e:
        checks["postgres"] = f"unhealthy: {str(e)}"

    # Check Redis
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL)
        try:
            pong = await redis_client.ping()
            checks["redis"] = "healthy" if pong else "unhealthy"
        finally:
            await redis_client.aclose()
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"

    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"

    return {
        "status": overall,
        "service": "api",
        "checks": checks,
    }


@router.get("/api/health")
async def api_health():
    """Simple API health check (for Caddy routing)."""
    return {"status": "healthy", "service": "api"}
