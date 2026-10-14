"""Job handler for processing source downloads."""

import os
import uuid
import logging
import asyncio
import httpx
from datetime import datetime

from app.config import settings
from app.services.db_service import db_service
from app.services.storage_service import storage_service
from app.providers.youtube import YoutubeProvider

logger = logging.getLogger(__name__)

async def handle_job(job_data: dict):
    source_id = job_data.get("source_id")
    platform = job_data.get("platform")
    url = job_data.get("url")
    project_id = job_data.get("project_id")
    
    if not source_id or not platform or not url or not project_id:
        logger.error(f"Invalid job data: {job_data}")
        return
        
    source = await db_service.get_source(source_id)
    if not source:
        logger.error(f"Source {source_id} not found in DB")
        return
        
    if source["status"] == "COMPLETED":
        logger.info(f"Source {source_id} is already completed")
        return
        
    # Check if downloading and stuck (stale job recovery check is typically done before enqueueing, but we can double check here)
    if source["status"] == "DOWNLOADING":
        # Maybe it's a retry from queue
        pass
        
    await db_service.update_source(source_id, "DOWNLOADING")
    
    # Check global retry count for catastrophic failures
    retry_count = source.get("retry_count", 0)
    if retry_count >= 3:
        await db_service.update_source(
            source_id, "FAILED", 
            error_code="MAX_RETRIES_EXCEEDED", 
            error_message="Maximum queue retry attempts exceeded."
        )
        return
        
    await db_service.increment_source_retry(source_id)

    # Temporary directory for download
    download_dir = os.path.join(settings.DOWNLOAD_TEMP_DIR, source_id)
    os.makedirs(download_dir, exist_ok=True)
    
    provider_adapter = None
    result = None
    upload_id = str(uuid.uuid4())
    
    try:
        logger.info(f"[Job {source_id}] Starting processing for {url}")
        
        if platform == "youtube":
            provider_adapter = YoutubeProvider()
            # YoutubeProvider now handles its own yt-dlp specific retries and backoffs
            result = await provider_adapter.download(url, download_dir)
            await db_service.log_download_attempt(
                source_id, provider_adapter.name, 
                "SUCCESS" if result.success else "FAILED", 
                retry_count + 1, result.error
            )
        elif platform == "instagram":
            from app.providers.instagram import InstagramProvider
            provider_adapter = InstagramProvider()
            result = await provider_adapter.download(url, download_dir)
            await db_service.log_download_attempt(
                source_id, provider_adapter.name, 
                "SUCCESS" if result.success else "FAILED", 
                retry_count + 1, result.error
            )
        else:
            raise NotImplementedError(f"Platform {platform} is not supported yet.")

        if not result or not result.success:
            # If youtube provider failed, it means it exhausted its retries or hit a fatal error.
            # We don't want to requeue it, we fail it immediately.
            error_msg = result.error if result else "Download failed"
            await db_service.update_source(
                source_id, "FAILED", 
                downloader_used=provider_adapter.name if provider_adapter else None,
                error_code="DOWNLOAD_FAILED",
                error_message=error_msg
            )
            return
            
        logger.info(f"[Job {source_id}] Processing complete. State: UPLOADING")
        await db_service.update_source(source_id, "UPLOADING")
            
        # Upload to MinIO
        folder = "videos" if result.content_type.startswith("video/") else "audios"
        object_key = f"projects/{project_id}/uploads/{folder}/{upload_id}_{result.original_filename}"
        
        logger.info(f"[Job {source_id}] Uploading {result.file_path} to {object_key}")
        storage_service.upload_file(result.file_path, object_key, result.content_type)
        
        # Create Upload Record
        pool = await db_service._get_pool()
        await pool.execute(
            """
            INSERT INTO uploads (
                id, project_id, source_id, original_filename, object_key,
                content_type, file_size, status
            ) VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6, $7, 'UPLOADING')
            """,
            uuid.UUID(upload_id), uuid.UUID(project_id), uuid.UUID(source_id),
            result.original_filename, object_key, result.content_type, result.file_size
        )
        
        # Mark as queued in uploads
        api_url = f"http://api:8000/api/uploads/{upload_id}/complete"
        async with httpx.AsyncClient() as client:
            resp = await client.post(api_url, timeout=30.0)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"API complete failed: {resp.text}")
                
        await db_service.update_source(source_id, "READY", downloader_used=provider_adapter.name)
        logger.info(f"[Job {source_id}] Successfully completed and uploaded.")

    except Exception as e:
        logger.error(f"[Job {source_id}] Job failed with exception: {e}")
        # If it failed during upload or unhandled exception
        await db_service.update_source(
            source_id, "FAILED", 
            downloader_used=provider_adapter.name if provider_adapter else None,
            error_code="UNHANDLED_EXCEPTION",
            error_message=str(e)
        )
            
    finally:
        # Cleanup
        import shutil
        try:
            shutil.rmtree(download_dir)
            logger.debug(f"[Job {source_id}] Cleaned up temp directory {download_dir}")
        except OSError:
            pass
