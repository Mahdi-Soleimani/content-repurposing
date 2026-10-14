import logging
import uuid
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.webhook import webhook_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ──── Models ────

class TextSubmitRequest(BaseModel):
    project_id: str
    content: str = Field(..., min_length=1, max_length=1000000) # limit to 1M chars
    idempotency_key: str | None = None

class UrlSubmitRequest(BaseModel):
    project_id: str
    url: HttpUrl
    idempotency_key: str | None = None

class ContentSubmitResponse(BaseModel):
    source_id: str
    status: str
    message: str


# ──── Endpoints ────

async def _trigger_webhook_async(event_id: str):
    """Background task to trigger webhook immediately after commit."""
    from app.database import async_session_maker
    async with async_session_maker() as db:
        await webhook_service.process_event(event_id, db)


@router.post("/text", response_model=ContentSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_text(
    request: TextSubmitRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Submit raw text for processing."""
    
    # Optional idempotency handling can go here later
    
    source_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    
    try:
        await db.execute(
            text("""
                INSERT INTO sources (
                    id, project_id, source_type, source_content, status
                ) VALUES (
                    :id, :project_id, 'text', :source_content, 'READY'
                )
            """),
            {
                "id": source_id,
                "project_id": request.project_id,
                "source_content": request.content,
            },
        )
        
        # Create webhook event payload
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "event": "text.submitted",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "source_id": source_id,
                "project_id": request.project_id,
                "source_type": "text",
                "content": request.content,
            }
        }
        
        # Try webhook synchronously FIRST
        from app.config import settings
        import httpx
        
        webhook_url = settings.N8N_WEBHOOK_URL
        webhook_success = False
        
        if webhook_url:
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    resp = await client.post(webhook_url, json=payload)
                    if resp.status_code in (200, 201, 202):
                        webhook_success = True
                except Exception as e:
                    logger.error(f"Failed to reach n8n webhook: {e}")
                    
        # Auto-create transcript for text input so it's immediately ready for content generation
        transcript_id = str(uuid.uuid4())
        await db.execute(
            text("""
                INSERT INTO transcripts (id, project_id, language, full_text, provider, model, content_status)
                VALUES (:id, :project_id, 'fa', :full_text, 'manual', 'text_input', 'READY')
            """),
            {
                "id": transcript_id,
                "project_id": request.project_id,
                "full_text": request.content,
            }
        )

        await db.execute(
            text("""
                INSERT INTO webhook_events (id, source_id, event_type, payload, status)
                VALUES (:id, :source_id, :event_type, :payload, 'SENT')
            """),
            {
                "id": event_id,
                "source_id": source_id,
                "event_type": "text.submitted",
                "payload": json.dumps(payload),
            }
        )
        
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Database error submitting text: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    return ContentSubmitResponse(
        source_id=source_id,
        status="SUBMITTED",
        message="Text submitted and queued for processing",
    )


@router.post("/url", response_model=ContentSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_url(
    request: UrlSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a URL for processing."""
    
    source_id = str(uuid.uuid4())
    normalized_url = str(request.url)
    
    # 1. Resolve Platform
    from urllib.parse import urlparse
    platform = 'unsupported'
    try:
        parsed = urlparse(normalized_url)
        domain = parsed.netloc.lower()
        if 'youtube.com' in domain or 'youtu.be' in domain:
            platform = 'youtube'
        elif 'instagram.com' in domain:
            platform = 'instagram'
    except Exception:
        pass

    if platform == 'unsupported':
        raise HTTPException(status_code=400, detail="Unsupported platform.")
    
    try:
        # 2. Insert Source
        await db.execute(
            text("""
                INSERT INTO sources (
                    id, project_id, source_type, source_url, platform, status
                ) VALUES (
                    :id, :project_id, 'url', :source_url, :platform, 'PENDING'
                )
            """),
            {
                "id": source_id,
                "project_id": request.project_id,
                "source_url": normalized_url,
                "platform": platform,
            },
        )
        
        # 3. Create webhook event payload
        import json
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "event": "url.submitted",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "source_id": source_id,
                "project_id": request.project_id,
                "source_type": "url",
                "platform": platform,
                "url": normalized_url,
            }
        }
        
        # Try webhook synchronously FIRST
        from app.config import settings
        import httpx
        
        webhook_url = settings.N8N_WEBHOOK_URL
        webhook_success = False
        
        if webhook_url:
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    resp = await client.post(webhook_url, json=payload)
                    if resp.status_code in (200, 201, 202):
                        webhook_success = True
                except Exception as e:
                    logger.error(f"Failed to reach n8n webhook: {e}")
                    
        if not webhook_success:
            await db.rollback()
            raise HTTPException(
                status_code=503, 
                detail="ارتباط با سرویس n8n برقرار نشد. لطفاً مطمئن شوید n8n روشن است و در حالت دریافت قرار دارد."
            )

        await db.execute(
            text("""
                INSERT INTO webhook_events (id, source_id, event_type, payload, status)
                VALUES (:id, :source_id, :event_type, :payload, 'SENT')
            """),
            {
                "id": event_id,
                "source_id": source_id,
                "event_type": "url.submitted",
                "payload": json.dumps(payload),
            }
        )
        
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Database error submitting URL: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    # 3. Enqueue to Redis
    try:
        from redis import asyncio as aioredis
        from app.config import settings
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        job_data = {
            "source_id": source_id,
            "platform": platform,
            "url": normalized_url,
            "project_id": request.project_id,
        }
        await redis.lpush("source_download_queue", json.dumps(job_data))
        await redis.close()
    except Exception as e:
        logger.error(f"Failed to enqueue source download: {e}")
        # Even if enqueue fails, source is in DB. We might need a dead letter queue or retry mechanism later.
        
    return ContentSubmitResponse(
        source_id=source_id,
        status="PENDING",
        message="URL submitted and queued for downloading",
    )
