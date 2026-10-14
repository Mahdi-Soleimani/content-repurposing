"""Redis Queue Consumer for Source Worker."""

import json
import logging
import asyncio
from redis import asyncio as aioredis
from typing import Callable, Awaitable

from app.config import settings

logger = logging.getLogger(__name__)

QUEUE_NAME = "source_download_queue"

class QueueConsumer:
    def __init__(self):
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self.is_running = False
        self._task = None
        self.handler: Callable[[dict], Awaitable[None]] = None

    def register_handler(self, handler: Callable[[dict], Awaitable[None]]):
        self.handler = handler

    async def start(self):
        """Start the background consumer."""
        if not self.handler:
            raise RuntimeError("Must register a handler before starting")
        
        self.is_running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("✅ Redis queue consumer started")

    async def stop(self):
        """Stop the background consumer."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.redis.close()
        logger.info("🛑 Redis queue consumer stopped")

    async def enqueue(self, job_data: dict):
        """Enqueue a job for processing."""
        await self.redis.rpush(QUEUE_NAME, json.dumps(job_data))

    async def _consume_loop(self):
        while self.is_running:
            try:
                # BLPOP blocks until a job is available or timeout (1s)
                result = await self.redis.blpop(QUEUE_NAME, timeout=1)
                if result:
                    _, item = result
                    job_data = json.loads(item)
                    logger.info(f"Received job: {job_data.get('source_id')}")
                    
                    # Fire handler and wait for it
                    try:
                        await self.handler(job_data)
                    except Exception as e:
                        logger.error(f"Error processing job {job_data}: {e}", exc_info=True)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis consumer error: {e}")
                await asyncio.sleep(1)

queue_consumer = QueueConsumer()
