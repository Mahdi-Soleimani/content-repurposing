import logging
import uuid
from typing import Dict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.database import get_db
from app.services.webhook import webhook_service

router = APIRouter(prefix="/projects/{project_id}/generation", tags=["generation"])
logger = logging.getLogger(__name__)

# ──── Models ────

class DraftUpdateRequest(BaseModel):
    requested_outputs: Dict[str, int]

class GenerateRequest(BaseModel):
    transcript_id: str
    requested_outputs: Dict[str, int]

class GenerationResponse(BaseModel):
    generation_job_id: str
    status: str
    message: str

# ──── Endpoints ────

@router.post("/{transcript_id}/discard")
async def discard_transcript(
    project_id: str,
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Marks a transcript as discarded and removes its source from the UI."""
    t_res = await db.execute(
        text("SELECT media_id, full_text FROM transcripts WHERE id = :id AND project_id = :project_id"),
        {"id": transcript_id, "project_id": project_id}
    )
    t_row = t_res.mappings().first()
    
    if not t_row:
        raise HTTPException(status_code=404, detail="Transcript not found")

    await db.execute(
        text("UPDATE transcripts SET content_status = 'DISCARDED', updated_at = NOW() WHERE id = :id"),
        {"id": transcript_id}
    )

    media_id = t_row.get("media_id")
    if media_id:
        # It's an upload or URL
        await db.execute(
            text("""
                UPDATE sources SET status = 'DISCARDED' 
                WHERE id = (SELECT source_id FROM media WHERE id = :media_id)
            """),
            {"media_id": str(media_id)}
        )
        try:
            await db.execute(
                text("""
                    UPDATE uploads SET status = 'DISCARDED' 
                    WHERE source_id = (SELECT source_id FROM media WHERE id = :media_id)
                """),
                {"media_id": str(media_id)}
            )
        except Exception:
            pass # Ignore if uploads table doesn't have source_id or something
    else:
        # It's a text input
        await db.execute(
            text("""
                UPDATE sources SET status = 'DISCARDED' 
                WHERE project_id = :project_id AND source_type = 'text' AND source_content = :full_text
            """),
            {"project_id": project_id, "full_text": t_row["full_text"]}
        )

    await db.commit()
    return {"status": "success", "message": "Transcript and source discarded."}


@router.put("/draft")
async def update_draft(
    project_id: str,
    request: DraftUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Upsert the generation draft for a project."""
    import json
    
    outputs_json = json.dumps(request.requested_outputs)

    await db.execute(
        text("""
            INSERT INTO generation_drafts (project_id, requested_outputs, updated_at)
            VALUES (:project_id, :outputs, NOW())
            ON CONFLICT (project_id) DO UPDATE 
            SET requested_outputs = EXCLUDED.requested_outputs, updated_at = NOW()
        """),
        {"project_id": project_id, "outputs": outputs_json}
    )
    await db.commit()
    
    return {"status": "success", "requested_outputs": request.requested_outputs}


def split_generation_request(requested_outputs: dict) -> list:
    """
    Converts requested output quantities into sequential single-unit payloads.
    Example: {"website_article": 2, "telegram": 1} -> [{"website_article": 1, "telegram": 1}, {"website_article": 1}]
    """
    payloads = []
    # Create a copy so we can decrement
    remaining = {k: v for k, v in requested_outputs.items() if v > 0}
    
    while any(v > 0 for v in remaining.values()):
        current_payload = {}
        for k, v in remaining.items():
            if v > 0:
                current_payload[k] = 1
                remaining[k] -= 1
        if current_payload:
            payloads.append(current_payload)
            
    return payloads if payloads else [{}]


@router.post("/generate", response_model=GenerationResponse)
async def generate_content(
    project_id: str,
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers content generation:
    1. Creates content_generation job in `jobs` table
    2. Triggers n8n webhook
    """
    import json
    
    total_requested = sum(int(count) for count in request.requested_outputs.values())
    if total_requested <= 0:
        raise HTTPException(status_code=400, detail="Please select at least one output to generate.")
        
    # 1. Fetch the transcript to get the text
    result = await db.execute(
        text("SELECT full_text FROM transcripts WHERE id = :transcript_id AND project_id = :project_id"),
        {"transcript_id": request.transcript_id, "project_id": project_id}
    )
    transcript_row = result.mappings().first()
    
    if not transcript_row:
        raise HTTPException(status_code=404, detail="Transcript not found")
        
    transcript_text = transcript_row["full_text"]
        
    job_id = str(uuid.uuid4())
    input_data = json.dumps({
        "transcript_id": request.transcript_id,
        "requested_outputs": request.requested_outputs
    })
    
    await db.execute(
        text("""
            UPDATE transcripts SET content_status = 'GENERATING', updated_at = NOW() WHERE id = :transcript_id
        """),
        {
            "transcript_id": request.transcript_id
        }
    )
    
    await db.execute(
        text("""
            INSERT INTO generation_jobs (id, project_id, status, requested_outputs, created_at)
            VALUES (:id, :project_id, 'PENDING', :requested_outputs, NOW())
        """),
        {
            "id": job_id,
            "project_id": project_id,
            "requested_outputs": json.dumps(request.requested_outputs)
        }
    )
    
    # 1. Commit the job to the database BEFORE sending the webhook
    await db.commit()
    
    # 3. Create webhook event payloads
    split_payloads = split_generation_request(request.requested_outputs)
    
    from app.config import settings
    import httpx
    
    webhook_url = settings.N8N_GENERATION_WEBHOOK_URL or settings.N8N_WEBHOOK_URL
    webhook_success = False
    sent_events = []
    error_detail = "Webhook URL not configured."
    
    if webhook_url:
        webhook_success = True
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                for single_request_outputs in split_payloads:
                    event_id = str(uuid.uuid4())
                    payload = {
                        "event_id": event_id,
                        "event": "generation.requested",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "data": {
                            "generation_job_id": job_id,
                            "project_id": project_id,
                            "transcript_id": request.transcript_id,
                            "transcript_text": transcript_text,
                            "requested_outputs": single_request_outputs
                        }
                    }
                    
                    resp = await client.post(webhook_url, json=payload)
                    if resp.status_code in (200, 201, 202):
                        sent_events.append({"id": event_id, "payload": payload})
                    else:
                        logger.warning(f"n8n webhook returned {resp.status_code}")
                        webhook_success = False
                        error_detail = f"n8n returned status code {resp.status_code}"
                        break # Stop on first failure
                        
            except Exception as e:
                logger.error(f"Failed to reach n8n webhook: {e}")
                webhook_success = False
                error_detail = str(e)
                
    # Record successful webhook events
    if sent_events:
        for ev in sent_events:
            await db.execute(
                text("""
                    INSERT INTO webhook_events (id, event_type, payload, status)
                    VALUES (:id, :event_type, :payload, 'SENT')
                """),
                {
                    "id": ev["id"],
                    "event_type": "generation.requested",
                    "payload": json.dumps(ev["payload"]),
                },
            )
        await db.commit()

    if not webhook_success:
        # Update job to FAILED since webhook failed
        await db.execute(
            text("""
                UPDATE generation_jobs SET status = 'FAILED', error_message = :err, completed_at = NOW() WHERE id = :jid
            """),
            {"err": error_detail, "jid": job_id}
        )
        await db.commit()
        raise HTTPException(
            status_code=503, 
            detail="ارتباط با سرویس n8n برقرار نشد. لطفاً مطمئن شوید n8n روشن است و در حالت دریافت (Listening) قرار دارد."
        )
    
    return GenerationResponse(
        generation_job_id=job_id,
        status="PENDING",
        message="Generation requested successfully."
    )
