"""Source Worker — Universal Content Ingestion Engine.

Handles downloading from YouTube, Instagram, and other sources.
Consumes jobs from Redis queue.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.services.queue import queue_consumer
from app.services.job_handler import handle_job
from app.services.db_service import db_service

async def stale_job_recovery_loop():
    timeout = int(os.getenv("JOB_STALE_TIMEOUT_SECONDS", "7200"))
    while True:
        try:
            await asyncio.sleep(60) # Check every 60 seconds
            await db_service.recover_stale_jobs(timeout)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in stale job recovery loop: {e}")

async def check_dependency(cmd: str) -> str:
    try:
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            # Return just the first line of output
            return stdout.decode().strip().split('\n')[0][:50]
        return f"Error: {stderr.decode().strip()[:50]}"
    except Exception as e:
        return f"Not installed ({str(e)})"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown tasks."""
    logger.info("🚀 Source Worker starting up...")
    
    # --- Startup Diagnostics ---
    logger.info("=== System Diagnostics ===")
    yt_dlp_version = await check_dependency("yt-dlp --version")
    ffmpeg_version = await check_dependency("ffmpeg -version")
    node_version = await check_dependency("node -v")
    
    cookies_file = os.getenv("YOUTUBE_COOKIES_FILE")
    cookies_status = "Enabled (File exists)" if cookies_file and os.path.exists(cookies_file) else (
        "Disabled (File not found)" if cookies_file else "Disabled (Env var not set)"
    )
    
    logger.info(f"yt-dlp version: {yt_dlp_version}")
    logger.info(f"ffmpeg version: {ffmpeg_version}")
    logger.info(f"node version: {node_version}")
    logger.info(f"YouTube Cookies: {cookies_status}")
    logger.info("==========================")
    
    queue_consumer.register_handler(handle_job)
    
    # Start stale job recovery task
    recovery_task = asyncio.create_task(stale_job_recovery_loop())
    
    await queue_consumer.start()
    yield
    
    recovery_task.cancel()
    try:
        await recovery_task
    except asyncio.CancelledError:
        pass
        
    await queue_consumer.stop()
    logger.info("🛑 Source Worker shutting down...")


app = FastAPI(
    title="Source Worker",
    description="Universal Content Ingestion Engine",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "source-worker"}


@app.post("/youtube/test")
async def test_youtube_connection():
    """Test YouTube connection and cookies by fetching metadata."""
    import subprocess
    import tempfile
    
    # We will use the storage service to get the cookies
    from app.services.storage_service import storage_service
    
    try:
        # Create a temporary file for the cookies
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_cookies:
            temp_cookies_path = temp_cookies.name
            
        try:
            # Try to download the cookies file from MinIO
            storage_service.download_file("secrets/youtube/cookies.txt", temp_cookies_path)
            cookies_arg = f"--cookies {temp_cookies_path}"
            logger.info("Using uploaded YouTube cookies for test.")
        except Exception as e:
            # If cookies don't exist or fail to download, we try without them
            logger.warning(f"Could not load cookies for test: {e}. Testing without cookies.")
            cookies_arg = ""
            
        # Run yt-dlp to just fetch the title of a known video (or generic fetch)
        # Using a reliable, lightweight video for testing
        test_video = "https://www.youtube.com/watch?v=jNQXAC9IVRw" # Me at the zoo
        
        cmd = f"yt-dlp {cookies_arg} --js-runtimes node --dump-json --no-warnings --simulate {test_video}"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=25.0)
        except asyncio.TimeoutError:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            return {
                "success": False,
                "message": "Connection test timed out",
                "details": "yt-dlp took too long to respond."
            }
        finally:
            if os.path.exists(temp_cookies_path):
                try:
                    os.remove(temp_cookies_path)
                except OSError:
                    pass
            
        if process.returncode == 0:
            return {
                "success": True, 
                "message": "YouTube access OK", 
                "details": "Successfully fetched metadata."
            }
        else:
            error_msg = stderr.decode().strip()
            # Check specifically for Bot Detection
            if "Sign in to confirm you’re not a bot" in error_msg or "The page needs to be reloaded" in error_msg:
                return {
                    "success": False,
                    "message": "Cookie missing or expired (Bot Detection Error)",
                    "details": error_msg
                }
            return {
                "success": False,
                "message": "YouTube access failed",
                "details": error_msg
            }
            
    except Exception as e:
        logger.error(f"Error testing youtube: {e}")
        return {"success": False, "message": "Internal worker error", "details": str(e)}
    finally:
        # Cleanup temp file
        if os.path.exists(temp_cookies_path):
            os.remove(temp_cookies_path)
