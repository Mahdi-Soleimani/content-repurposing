"""FastAPI Backend — Content Repurposing Platform."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, async_session_maker
from app.routers import health, projects, uploads, content, generation
from app.routers import settings as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: verify DB connection
    async with engine.begin() as conn:
        result = await conn.execute(
            __import__("sqlalchemy").text("SELECT 1")
        )
        assert result.scalar() == 1, "Database connection failed"
    print("✅ Database connection verified")

    # Startup: verify Redis connection
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(settings.REDIS_URL)
    try:
        pong = await redis_client.ping()
        assert pong is True, "Redis connection failed"
        print("✅ Redis connection verified")
    finally:
        await redis_client.aclose()

    # Startup: Init S3 bucket
    from app.services.storage import storage_service
    try:
        storage_service.ensure_bucket_exists()
        storage_service.set_bucket_public_read()
        print(f"✅ S3 Bucket '{settings.S3_BUCKET_NAME}' verified and public")
    except Exception as e:
        print(f"⚠️ S3 Bucket initialization failed: {e}")

    # Startup: Start Webhook Worker
    from app.services.webhook_worker import start_webhook_worker, stop_webhook_worker
    start_webhook_worker()
    print("✅ Webhook worker started")

    yield

    # Shutdown
    await stop_webhook_worker()
    print("🛑 Webhook worker stopped")
    await engine.dispose()
    from app.services.webhook import webhook_service
    await webhook_service.close()
    print("🛑 Database connection closed")


app = FastAPI(
    title="Content Repurposing API",
    description="Backend API for the Content Repurposing Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(generation.router, prefix="/api")


@app.get("/")
async def root():
    return {"service": "content-repurposing-api", "status": "running"}
