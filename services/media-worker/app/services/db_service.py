"""Database service for media-worker — direct asyncpg writes.

Media Worker only writes to these tables:
  ✅ media
  ✅ transcripts
  ✅ uploads.status
  ✅ sources.status
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)


class DBService:
    """Direct PostgreSQL access for persisting media processing results."""

    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            # Convert async SQLAlchemy URL to plain asyncpg URL
            dsn = settings.DATABASE_URL
            if dsn.startswith("postgresql+asyncpg://"):
                dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
            self._pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()

    # ──── Media ────

    async def insert_media(
        self,
        project_id: str,
        source_id: str,
        upload_id: str,
        media_type: str,
        storage_key: str,
        mime_type: str | None = None,
        duration_seconds: float | None = None,
        width: int | None = None,
        height: int | None = None,
        size_bytes: int | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Insert a media record. Returns media_id."""
        pool = await self._get_pool()
        media_id = str(uuid.uuid4())
        await pool.execute(
            """
            INSERT INTO media (id, project_id, source_id, media_type, object_key,
                               mime_type, duration_seconds, resolution, file_size, metadata)
            VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10::jsonb)
            """,
            uuid.UUID(media_id),
            uuid.UUID(project_id),
            uuid.UUID(source_id),
            media_type,
            storage_key,
            mime_type,
            duration_seconds,
            f"{width}x{height}" if width and height else None,
            size_bytes,
            json.dumps(metadata or {}),
        )
        logger.info(f"Inserted media {media_id} for project {project_id}")
        return media_id

    # ──── Transcripts ────

    async def insert_transcript(
        self,
        project_id: str,
        media_id: str,
        source_id: str | None = None,
        language: str = "fa",
        text: str = "",
        segments: list | None = None,
        duration_seconds: float | None = None,
        provider: str = "",
        model: str = "",
        status: str = "COMPLETED",
        metadata: dict | None = None,
    ) -> str:
        """Insert a transcript record. Returns transcript_id."""
        pool = await self._get_pool()
        transcript_id = str(uuid.uuid4())
        
        # Map worker status to UI's content_status expectations
        content_status = "READY" if status == "COMPLETED" else status

        await pool.execute(
            """
            INSERT INTO transcripts (id, media_id, project_id, language, full_text,
                                     segments, provider, model, confidence, content_status, metadata)
            VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6::jsonb, $7, $8, $9, $10, $11::jsonb)
            """,
            uuid.UUID(transcript_id),
            uuid.UUID(media_id),
            uuid.UUID(project_id),
            language,
            text,
            json.dumps(segments or []),
            provider,
            model,
            None,  # confidence
            content_status,
            json.dumps(metadata or {}),
        )
        logger.info(f"Inserted transcript {transcript_id} for project {project_id}")
        return transcript_id

    # ──── Status Updates ────

    async def update_upload_status(self, upload_id: str, status: str, error_message: str | None = None):
        """Update uploads.status."""
        pool = await self._get_pool()
        await pool.execute(
            "UPDATE uploads SET status = $1, error_message = $2, updated_at = NOW() WHERE id = $3",
            status, error_message, uuid.UUID(upload_id),
        )
        logger.info(f"Updated upload {upload_id} status → {status}")

    async def update_source_status(self, source_id: str, status: str):
        """Update sources.status."""
        pool = await self._get_pool()
        await pool.execute(
            "UPDATE sources SET status = $1, updated_at = NOW() WHERE id = $2",
            status, uuid.UUID(source_id),
        )
        logger.info(f"Updated source {source_id} status → {status}")

    # ──── Idempotency ────

    async def get_existing_transcript(self, upload_id: str) -> dict | None:
        """Check if a completed transcript already exists for this upload.

        Prevents duplicate processing on retry.
        """
        pool = await self._get_pool()
        row = await pool.fetchrow(
            """
            SELECT t.id as transcript_id, m.id as media_id, m.media_type,
                   m.duration_seconds, t.language
            FROM media m
            JOIN transcripts t ON t.media_id = m.id
            WHERE m.object_key LIKE '%' || $1 || '%'
            LIMIT 1
            """,
            upload_id,
        )
        if row:
            return dict(row)
        return None

    # ──── Jobs ────

    async def get_job(self, job_id: str) -> dict | None:
        """Fetch a job by ID."""
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT * FROM jobs WHERE id = $1::uuid", uuid.UUID(job_id))
        return dict(row) if row else None

    async def update_job_status(self, job_id: str, status: str, provider: str | None = None, model: str | None = None, error: str | None = None):
        """Update job status and optional fields."""
        pool = await self._get_pool()
        
        updates = ["status = $2", "updated_at = NOW()"]
        params = [uuid.UUID(job_id), status]
        
        if provider:
            params.append(provider)
            updates.append(f"provider = ${len(params)}")
            
        if model:
            params.append(model)
            updates.append(f"model = ${len(params)}")
            
        if error:
            params.append(error)
            updates.append(f"error_message = ${len(params)}")
            
        if status == "PROCESSING":
            updates.append("started_at = NOW()")
        elif status in ["COMPLETED", "FAILED"]:
            updates.append("completed_at = NOW()")
            
        set_clause = ", ".join(updates)
        await pool.execute(f"UPDATE jobs SET {set_clause} WHERE id = $1", *params)

    async def get_upload_details(self, upload_id: str) -> dict | None:
        """Fetch upload details."""
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT project_id, source_id, object_key FROM uploads WHERE id = $1::uuid", uuid.UUID(upload_id))
        return dict(row) if row else None

    # ──── Processing Usage ────
    
    async def insert_processing_usage(
        self,
        project_id: str,
        job_id: str | None,
        provider: str,
        model: str,
        duration_seconds: float = 0,
        audio_seconds: float = 0,
        input_size_bytes: int = 0,
        tokens_used: int = 0,
        cost: float = 0,
    ):
        """Record cost and usage metrics."""
        pool = await self._get_pool()
        await pool.execute(
            """
            INSERT INTO processing_usage (
                project_id, job_id, provider, model, duration_seconds, audio_seconds, input_size_bytes, tokens_used, cost
            ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(project_id),
            uuid.UUID(job_id) if job_id else None,
            provider,
            model,
            duration_seconds,
            audio_seconds,
            input_size_bytes,
            tokens_used,
            cost,
        )
db_service = DBService()
