"""Targeted unit tests for Redis Queue Consumer in Source Worker."""

import asyncio
import json
from unittest.mock import AsyncMock

from app.services.queue import QueueConsumer, QUEUE_NAME


def test_enqueue_serializes_and_calls_rpush():
    async def run():
        mock_redis = AsyncMock()
        consumer = QueueConsumer()
        consumer.redis = mock_redis

        test_job = {"source_id": "src_123", "url": "https://youtube.com/watch?v=abc"}
        await consumer.enqueue(test_job)

        mock_redis.rpush.assert_awaited_once_with(QUEUE_NAME, json.dumps(test_job))

    asyncio.run(run())


def test_consume_loop_processes_job_successfully():
    async def run():
        mock_redis = AsyncMock()
        consumer = QueueConsumer()
        consumer.redis = mock_redis

        test_job = {"source_id": "src_456", "type": "youtube"}
        mock_redis.blpop.side_effect = [
            (QUEUE_NAME, json.dumps(test_job)),
            asyncio.CancelledError(),
        ]

        handled_jobs = []

        async def mock_handler(job_data):
            handled_jobs.append(job_data)

        consumer.register_handler(mock_handler)
        consumer.is_running = True

        await consumer._consume_loop()

        assert len(handled_jobs) == 1
        assert handled_jobs[0] == test_job
        assert mock_redis.blpop.await_count == 2

    asyncio.run(run())


def test_consume_loop_handles_timeout_gracefully():
    async def run():
        mock_redis = AsyncMock()
        consumer = QueueConsumer()
        consumer.redis = mock_redis

        # Return None on timeout, then cancel
        mock_redis.blpop.side_effect = [None, asyncio.CancelledError()]

        handled_jobs = []

        async def mock_handler(job):
            handled_jobs.append(job)

        consumer.register_handler(mock_handler)
        consumer.is_running = True

        await consumer._consume_loop()

        assert len(handled_jobs) == 0
        assert mock_redis.blpop.await_count == 2

    asyncio.run(run())


def test_consume_loop_handles_malformed_json_without_crashing():
    async def run():
        mock_redis = AsyncMock()
        consumer = QueueConsumer()
        consumer.redis = mock_redis

        # Malformed JSON payload followed by cancellation
        mock_redis.blpop.side_effect = [
            (QUEUE_NAME, "not-valid-json{{"),
            asyncio.CancelledError(),
        ]

        handled_jobs = []

        async def mock_handler(job):
            handled_jobs.append(job)

        consumer.register_handler(mock_handler)
        consumer.is_running = True

        await consumer._consume_loop()

        # Handler should not have been called, and consumer caught exception
        assert len(handled_jobs) == 0

    asyncio.run(run())


def test_stop_closes_redis_connection():
    async def run():
        mock_redis = AsyncMock()
        consumer = QueueConsumer()
        consumer.redis = mock_redis

        await consumer.stop()

        assert mock_redis.close.await_count == 1

    asyncio.run(run())
