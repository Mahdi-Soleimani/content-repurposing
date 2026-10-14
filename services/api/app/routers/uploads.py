"""Upload endpoints — full upload lifecycle (V2).

Flow:
    POST /api/uploads/init         → Create upload, get presigned URL
    POST /api/uploads/{id}/complete → Verify in S3, update DB, create webhook event in transaction
    GET  /api/uploads/{id}         → Status polling
    GET  /api/uploads/             → List all uploads
"""

import logging
import uuid
import asyncio
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.storage import storage_service
from app.services.webhook import webhook_service

logger = logging.getLogger(__name__)

async def trigger_media_worker(job_id: str, media_worker_url: str):
    import httpx
    if not media_worker_url:
        logger.error("No MEDIA_WORKER_URL configured")
        return
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{media_worker_url}/media/process", 
                json={"job_id": job_id},
                timeout=5.0
            )
            if resp.status_code == 200:
                logger.info(f"Triggered media-worker for job {job_id}")
            else:
                logger.error(f"Failed to trigger media-worker: {resp.text}")
    except Exception as e:
        logger.error(f"Exception triggering media-worker: {e}")

router = APIRouter()


# ──── Enums ────

class UploadStatus(str, Enum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ──── Request/Response Models ────

class UploadInitRequest(BaseModel):
    project_id: str
    filename: str
    content_type: str = "video/mp4"
    file_size: int | None = None


class UploadInitResponse(BaseModel):
    upload_id: str
    object_key: str
    upload_url: str
    method: str = "PUT"
    status: str = "UPLOADING"


class UploadCompleteResponse(BaseModel):
    upload_id: str
    status: str
    object_key: str
    file_size: int | None = None
    message: str = "Upload completed and queued for processing"


class UploadStatusResponse(BaseModel):
    upload_id: str
    project_id: str
    original_filename: str
    object_key: str
    content_type: str
    file_size: int | None = None
    status: str
    download_url: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


# ──── Helpers ────

def _detect_media_type(content_type: str) -> str:
    """Detect media type from MIME content type."""
    if content_type.startswith("video/"):
        return "video"
    elif content_type.startswith("audio/"):
        return "audio"
    elif content_type.startswith("image/"):
        return "image"
    elif content_type.startswith("text/") or content_type in (
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        return "document"
    return "other"


def _generate_object_key(project_id: str, upload_id: str, filename: str, content_type: str) -> str:
    """Generate a structured S3 object key."""
    safe_filename = filename.replace("/", "_").replace("\\", "_")
    media_type = _detect_media_type(content_type)
    subfolder = "videos" if media_type == "video" else "audios" if media_type == "audio" else "others"
    return f"projects/{project_id}/uploads/{subfolder}/{upload_id}_{safe_filename}"


# ──── Endpoints ────

@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    request: UploadInitRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initialize a direct upload.
    Creates a source (type=media) + upload record in one transaction.
    Returns a presigned URL.
    """
    source_id = str(uuid.uuid4())
    upload_id = str(uuid.uuid4())
    object_key = _generate_object_key(
        request.project_id, upload_id, request.filename, request.content_type
    )

    upload_url = storage_service.generate_presigned_upload_url(
        object_key=object_key,
        content_type=request.content_type,
    )

    # Create source (type=media) first
    await db.execute(
        text("""
            INSERT INTO sources (
                id, project_id, source_type, original_filename, status
            ) VALUES (
                :id, :project_id, 'media', :original_filename, 'UPLOADING'
            )
        """),
        {
            "id": source_id,
            "project_id": request.project_id,
            "original_filename": request.filename,
        },
    )

    # Create upload linked to source
    await db.execute(
        text("""
            INSERT INTO uploads (
                id, project_id, source_id, original_filename, object_key,
                content_type, file_size, status
            ) VALUES (
                :id, :project_id, :source_id, :original_filename, :object_key,
                :content_type, :file_size, :status
            )
        """),
        {
            "id": upload_id,
            "project_id": request.project_id,
            "source_id": source_id,
            "original_filename": request.filename,
            "object_key": object_key,
            "content_type": request.content_type,
            "file_size": request.file_size,
            "status": UploadStatus.UPLOADING.value,
        },
    )
    await db.commit()

    logger.info(
        f"Upload initialized: upload_id={upload_id}, source_id={source_id}, "
        f"object_key={object_key}, project={request.project_id}"
    )

    return UploadInitResponse(
        upload_id=upload_id,
        object_key=object_key,
        upload_url=upload_url,
    )


async def _trigger_webhook_async(event_id: str):
    """Background task to trigger webhook immediately after commit."""
    # We create a new DB session for the background task
    from app.database import async_session_maker
    async with async_session_maker() as db:
        await webhook_service.process_event(event_id, db)


@router.post("/{upload_id}/complete", response_model=UploadCompleteResponse)
async def complete_upload(
    upload_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    [INTERNAL WORKER CALLBACK] Confirm upload completion.
    1. Verifies in S3
    2. Updates status to UPLOADED and then QUEUED
    3. Inserts into webhook_events in same transaction
    4. Commits and triggers n8n asynchronously
    """
    # 1. Get upload record
    result = await db.execute(
        text("""
            SELECT id, project_id, source_id, original_filename, object_key,
                   content_type, file_size, status, metadata
            FROM uploads WHERE id = :id FOR UPDATE
        """),
        {"id": upload_id},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Idempotency: if already processed, return success
    if row["status"] in (
        UploadStatus.UPLOADED.value,
        UploadStatus.QUEUED.value,
        UploadStatus.PROCESSING.value,
        UploadStatus.COMPLETED.value,
    ):
        return UploadCompleteResponse(
            upload_id=upload_id,
            status=row["status"],
            object_key=row["object_key"],
            file_size=row["file_size"],
            message="Upload already completed"
        )

    if row["status"] not in (
        UploadStatus.UPLOADING.value,
        UploadStatus.CREATED.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Upload in invalid status for completion: {row['status']}",
        )

    object_key = row["object_key"]

    # 2. Verify file exists in S3
    try:
        if not storage_service.verify_object_exists(object_key):
            await db.execute(
                text("""
                    UPDATE uploads
                    SET status = :status, error_message = :error
                    WHERE id = :id
                """),
                {
                    "id": upload_id,
                    "status": UploadStatus.FAILED.value,
                    "error": "File not found in object storage after upload",
                },
            )
            await db.commit()
            raise HTTPException(
                status_code=400,
                detail="File not found in object storage. Upload may have failed.",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Failed to verify object {object_key} in S3: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Storage service error: {e}",
        )

    try:
        obj_meta = storage_service.get_object_metadata(object_key)
    except Exception as e:
        logger.error(f"Failed to get metadata for object {object_key} in S3: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Storage service error getting metadata: {e}",
        )
    actual_size = obj_meta["content_length"] if obj_meta else row["file_size"]
    media_type = _detect_media_type(row["content_type"])

    # 2.5 Fetch project stt_provider
    proj_result = await db.execute(
        text("SELECT stt_provider FROM projects WHERE id = :id"),
        {"id": row["project_id"]}
    )
    proj_row = proj_result.mappings().first()
    stt_provider = proj_row["stt_provider"] if proj_row else "shenava"

    model = "Shenava-Koochik-v1.5" if stt_provider == "shenava" else "whisper-1"
    
    # 3. Transaction: Update uploads, Create job AND insert webhook event
    event_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    
    payload = {
        "event_id": event_id,
        "event": "job.created",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": {
            "type": "transcription",
            "job": {
                "id": job_id,
                "provider": stt_provider,
                "model": model
            },
            "project": {
                "id": str(row["project_id"])
            },
            "upload": {
                "id": upload_id,
                "media_type": media_type,
                "content_type": row["content_type"],
                "file_size": actual_size,
                "original_filename": row["original_filename"],
                "object_key": object_key
            }
        }
    }
    
    import json
    
    # Merge existing metadata with new S3 metadata
    db_metadata = dict(row["metadata"]) if row["metadata"] else {}
    if obj_meta:
        db_metadata.update({
            "etag": obj_meta.get("etag"),
            "storage": "minio",
            "verified_at": datetime.utcnow().isoformat() + "Z",
        })

    try:
        # Update uploads to QUEUED since it's ready for processing
        await db.execute(
            text("""
                UPDATE uploads
                SET status = :status, file_size = :file_size, metadata = :metadata
                WHERE id = :id
            """),
            {
                "id": upload_id,
                "status": UploadStatus.QUEUED.value,
                "file_size": actual_size,
                "metadata": json.dumps(db_metadata),
            },
        )
        
        # Insert into jobs
        await db.execute(
            text("""
                INSERT INTO jobs (id, project_id, upload_id, job_type, status, provider, model)
                VALUES (:id, :project_id, :upload_id, :job_type, 'queued', :provider, :model)
            """),
            {
                "id": job_id,
                "project_id": row["project_id"],
                "upload_id": upload_id,
                "job_type": "transcription",
                "provider": stt_provider,
                "model": model,
            }
        )
        
        # Create webhook event payload
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "event": "job.created",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "upload": {
                    "id": upload_id,
                    "media_type": row["content_type"]
                },
                "job": {
                    "id": job_id
                },
                "project_id": str(row["project_id"])
            }
        }
        
        # Try the webhook synchronously FIRST before committing
        from app.config import settings
        import httpx
        
        webhook_url = settings.N8N_WEBHOOK_URL
        webhook_success = False
        
        if webhook_url:
            async with httpx.AsyncClient(timeout=3.0) as client:
                try:
                    resp = await client.post(webhook_url, json=payload)
                    if resp.status_code in (200, 201, 202):
                        webhook_success = True
                    else:
                        logger.warning(f"n8n webhook returned {resp.status_code}")
                except Exception as e:
                    logger.warning(f"Failed to reach n8n webhook: {e}")
                    
        # Always commit the webhook event so it can be retried if n8n is offline
        await db.execute(
            text("""
                INSERT INTO webhook_events (id, upload_id, event_type, payload, status)
                VALUES (:id, :upload_id, :event_type, :payload, :status)
            """),
            {
                "id": event_id,
                "upload_id": upload_id,
                "event_type": "job.created",
                "payload": json.dumps(payload),
                "status": 'SENT' if webhook_success else 'PENDING'
            }
        )
        
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to commit upload completion transaction: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

    # 4. Create Job and trigger media-worker directly
    try:
        media_job_id = str(uuid.uuid4())
        await db.execute(
            text("""
                INSERT INTO jobs (id, project_id, upload_id, job_type, status, provider, model)
                VALUES (:id, :project_id, :upload_id, 'media_process', 'pending', :provider, :model)
            """),
            {
                "id": media_job_id,
                "project_id": str(row["project_id"]),
                "upload_id": upload_id,
                "provider": stt_provider,
                "model": model,
            }
        )
        await db.commit()
        
        from app.config import settings
        media_url = getattr(settings, "MEDIA_WORKER_URL", "http://media-worker:8001")
        background_tasks.add_task(trigger_media_worker, media_job_id, media_url)
        logger.info(f"Created job {media_job_id} and triggered media-worker for upload {upload_id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create job or trigger media-worker: {e}")

    logger.info(
        f"Upload completed & queued: upload_id={upload_id}, size={actual_size}"
    )



    return UploadCompleteResponse(
        upload_id=upload_id,
        status=UploadStatus.QUEUED.value,
        object_key=object_key,
        file_size=actual_size,
    )




class UploadStatusUpdateRequest(BaseModel):
    status: UploadStatus
    error_message: str | None = None

@router.patch("/{upload_id}/status")
async def update_upload_status(
    upload_id: str,
    request: UploadStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    [INTERNAL WORKER CALLBACK] Update upload status.
    Used by n8n or background workers.
    """
    result = await db.execute(
        text("UPDATE uploads SET status = :status, error_message = :error, updated_at = NOW() WHERE id = :id RETURNING id"),
        {
            "id": upload_id,
            "status": request.status.value,
            "error": request.error_message,
        }
    )
    if not result.first():
        raise HTTPException(status_code=404, detail="Upload not found")
    await db.commit()
    return {"message": "Status updated successfully"}

