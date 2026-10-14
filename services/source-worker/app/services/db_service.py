"""Database service for source-worker."""

import uuid
import logging
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)

class DBService:
    def __init__(self):
        self._pool = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            dsn = settings.DATABASE_URL
            if dsn.startswith("postgresql+asyncpg://"):
                dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
            self._pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()

    async def get_source(self, source_id: str) -> dict | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT * FROM sources WHERE id = $1::uuid", uuid.UUID(source_id))
        return dict(row) if row else None

    async def update_source(self, source_id: str, status: str, downloader_used: str = None, error_code: str = None, error_message: str = None):
        pool = await self._get_pool()
        
        updates = ["status = $2", "updated_at = NOW()"]
        params = [uuid.UUID(source_id), status]
        
        if downloader_used:
            params.append(downloader_used)
            updates.append(f"downloader_used = ${len(params)}")
            
        if error_code:
            params.append(error_code)
            updates.append(f"error_code = ${len(params)}")
            
        if error_message:
            params.append(error_message)
            updates.append(f"error_message = ${len(params)}")
            
        set_clause = ", ".join(updates)
        await pool.execute(f"UPDATE sources SET {set_clause} WHERE id = $1", *params)

    async def log_download_attempt(self, source_id: str, provider: str, status: str, attempt_count: int = 1, error_message: str = None):
        pool = await self._get_pool()
        await pool.execute(
            """
            INSERT INTO downloads (source_id, provider, status, attempt_count, error_message, completed_at)
            VALUES ($1::uuid, $2, $3, $4, $5, NOW())
            """,
            uuid.UUID(source_id), provider, status, attempt_count, error_message
        )

    async def increment_source_retry(self, source_id: str):
        pool = await self._get_pool()
        await pool.execute("UPDATE sources SET retry_count = retry_count + 1 WHERE id = $1::uuid", uuid.UUID(source_id))

    async def recover_stale_jobs(self, timeout_seconds: int):
        pool = await self._get_pool()
        stale_jobs = await pool.fetch(
            f"""
            SELECT id, platform, source_url as url, project_id, retry_count FROM sources 
            WHERE status IN ('DOWNLOADING', 'UPLOADING') 
            AND updated_at < NOW() - INTERVAL '{timeout_seconds} seconds'
            """
        )
        
        if not stale_jobs:
            return

        from app.services.queue import queue_consumer
            
        for job in stale_jobs:
            source_id = str(job['id'])
            retry_count = job.get('retry_count', 0)
            
            logger.warning(f"Detected stale job {source_id} (retry_count: {retry_count})")
            
            if retry_count >= 3:
                await self.update_source(
                    source_id, "FAILED",
                    error_code="STALE_JOB_TIMEOUT",
                    error_message="Job stuck in processing state for too long and exceeded max retries."
                )
                logger.error(f"Stale job {source_id} marked as FAILED (max retries exceeded).")
            else:
                await self.increment_source_retry(source_id)
                await self.update_source(
                    source_id, "PENDING",
                    error_code="STALE_JOB_RECOVERED",
                    error_message="Job was stuck, recovered to PENDING."
                )
                logger.info(f"Stale job {source_id} recovered to PENDING. Re-enqueueing...")
                
                # Requeue it
                job_data = {
                    "source_id": source_id,
                    "platform": job["platform"],
                    "url": job["url"],
                    "project_id": str(job["project_id"]) if job.get("project_id") else None
                }
                await queue_consumer.enqueue(job_data)

db_service = DBService()
