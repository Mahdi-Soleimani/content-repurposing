"""Media Worker — Content Repurposing Platform.

Handles heavy media processing: FFmpeg, transcription via AvalAI/OpenAI.

Endpoints:
    POST /media/process  → Full pipeline: Download → Detect → Normalize → STT → Persist
    GET  /health         → Health check
"""

import logging
import shutil
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.media_pipeline import media_pipeline
from app.services.db_service import db_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify tools on startup, cleanup on shutdown."""
    # Check FFmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
        logger.info(f"✅ FFmpeg available: {version_line}")
    else:
        logger.warning("❌ FFmpeg not found!")

    # Check yt-dlp
    ytdlp_path = shutil.which("yt-dlp")
    if ytdlp_path:
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        version = result.stdout.strip() if result.stdout else "unknown"
        logger.info(f"✅ yt-dlp available: {version}")
    else:
        logger.info("ℹ️  yt-dlp not found (optional)")

    # Validate STT Provider
    from app.services.transcription import ProviderFactory
    from app.config import settings
    
    provider_name = settings.STT_PROVIDER
    logger.info(f"Checking STT Provider: {provider_name}")
    try:
        prov = ProviderFactory.create(provider_name)
        is_avail = await prov.is_available()
        if not is_avail:
            logger.error(f"❌ Provider {provider_name} failed availability check!")
            # Note: We do not hard-crash FastAPI, but log prominently.
        else:
            logger.info(f"✅ Provider {provider_name} is available.")
    except Exception as e:
        logger.error(f"❌ Failed to load provider {provider_name}: {e}")

    yield

    # Cleanup
    await db_service.close()
    logger.info("🛑 Media Worker shutting down")


app = FastAPI(
    title="Media Worker",
    description="Media processing service: FFmpeg → AvalAI STT → PostgreSQL",
    version="0.2.0",
    lifespan=lifespan,
)


# ──── Request/Response Models ────

class MediaProcessRequest(BaseModel):
    job_id: str


class MediaProcessResponse(BaseModel):
    status: str
    job_id: str
    upload_id: str | None = None
    source_id: str | None = None
    media_id: str | None = None
    transcript_id: str | None = None
    media_type: str | None = None
    duration_seconds: float | None = None
    language: str | None = None
    error: str | None = None


# ──── Endpoints ────

@app.get("/health")
async def health():
    """Health check with tool availability."""
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ytdlp_ok = shutil.which("yt-dlp") is not None
    return {
        "status": "healthy" if ffmpeg_ok else "degraded",
        "service": "media-worker",
        "version": "0.2.0",
        "tools": {
            "ffmpeg": "available" if ffmpeg_ok else "missing",
            "yt-dlp": "available" if ytdlp_ok else "missing",
        },
    }


@app.post("/media/process", response_model=MediaProcessResponse)
async def process_media(request: MediaProcessRequest, background_tasks: BackgroundTasks):
    """Trigger the full media processing pipeline asynchronously.

    Input (from n8n):
        - job_id: UUID of the job record

    Pipeline:
        Fetch Job → MinIO → ffprobe → FFmpeg Normalize → Chunk → STT → PostgreSQL
    """
    # 1. Validate job existence first to fail fast
    job = await db_service.get_job(request.job_id)
    if not job:
        logger.error(f"Failed to queue processing: Job {request.job_id} not found in DB")
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Accepted request, queuing background processing: job_id={request.job_id}")

    # Fire and forget: run the heavy pipeline in the background
    background_tasks.add_task(media_pipeline.process, job_id=request.job_id)

    # Return immediately to n8n
    return MediaProcessResponse(
        status="processing",
        job_id=request.job_id
    )
