"""Background worker for retrying failed webhook events."""

import asyncio
import logging

from sqlalchemy import text

from app.database import async_session_maker
from app.services.webhook import webhook_service

logger = logging.getLogger(__name__)

# Max attempts: 3
MAX_ATTEMPTS = 3
# Backoff delays in seconds for attempt 1, 2, 3 (already done attempt 1 immediately)
# If attempt=1 (failed once), wait 30s. If attempt=2 (failed twice), wait 300s (5m).
BACKOFF_DELAYS = {
    1: 30,
    2: 300,
}


async def process_pending_and_failed_webhooks():
    """Background task to poll and retry webhooks."""
    logger.info("🚀 Webhook background worker started")
    while True:
        try:
            async with async_session_maker() as db:
                # Find events that need processing
                # Either PENDING, or FAILED with attempts < MAX_ATTEMPTS and old enough
                
                # PostgreSQL specific query using interval
                # PENDING is picked up immediately (though normally sent directly)
                # FAILED is picked up based on attempts
                query = text("""
                    SELECT id, status, attempts, EXTRACT(EPOCH FROM (NOW() - updated_at)) as age_seconds
                    FROM webhook_events
                    WHERE status = 'PENDING'
                       OR (status = 'FAILED' AND attempts < :max_attempts)
                    ORDER BY created_at ASC
                    LIMIT 50
                """)
                result = await db.execute(query, {"max_attempts": MAX_ATTEMPTS})
                events = result.mappings().all()

                for event in events:
                    should_process = False
                    if event["status"] == "PENDING":
                        should_process = True
                    elif event["status"] == "FAILED":
                        attempts = event["attempts"]
                        age = event["age_seconds"]
                        required_delay = BACKOFF_DELAYS.get(attempts, 300)
                        if age >= required_delay:
                            should_process = True
                    
                    if should_process:
                        logger.info(f"🔄 Retrying webhook event {event['id']} (attempt {event['attempts'] + 1})")
                        # process_event handles the transaction and locks the row
                        await webhook_service.process_event(str(event["id"]), db)
                        
        except Exception as e:
            logger.error(f"❌ Error in webhook worker: {e}")
        
        # Sleep before next poll
        await asyncio.sleep(10)


_worker_task = None


def start_webhook_worker():
    """Start the background worker."""
    global _worker_task
    loop = asyncio.get_running_loop()
    _worker_task = loop.create_task(process_pending_and_failed_webhooks())


async def stop_webhook_worker():
    """Stop the background worker."""
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
