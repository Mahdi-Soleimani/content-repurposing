"""n8n Webhook notification service.

Handles sending events to n8n and updating webhook_events status in DB.
"""

import logging

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


class WebhookService:
    """Sends webhook notifications to n8n."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
        return self._client

    async def process_event(self, event_id: str, db: AsyncSession) -> bool:
        """
        Send a specific webhook event from the database.
        Returns True if successful, False otherwise.
        """
        # Fetch event
        result = await db.execute(
            text("""
                SELECT id, event_type, payload, status, attempts
                FROM webhook_events
                WHERE id = :id FOR UPDATE SKIP LOCKED
            """),
            {"id": event_id},
        )
        event = result.mappings().first()

        if not event:
            return False

        if event["status"] == "SENT":
            return True

        # Mark as PROCESSING immediately
        await db.execute(
            text("UPDATE webhook_events SET status = 'PROCESSING' WHERE id = :id"),
            {"id": event_id}
        )
        await db.commit()

        webhook_url = settings.N8N_WEBHOOK_URL
        if event["event_type"] == "generation.requested" and settings.N8N_GENERATION_WEBHOOK_URL:
            webhook_url = settings.N8N_GENERATION_WEBHOOK_URL
            
        attempts = event["attempts"] + 1
        last_error = None
        success = False

        try:
            response = await self.client.post(
                webhook_url,
                json=event["payload"],
            )

            if response.status_code in (200, 201, 202):
                logger.info(
                    f"✅ Webhook event sent successfully "
                    f"(event_id={event_id}, type={event['event_type']})"
                )
                success = True
            else:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    f"⚠️ Webhook returned {response.status_code} "
                    f"(event_id={event_id}, attempt={attempts})"
                )

        except httpx.ConnectError as e:
            last_error = f"Connection error: {str(e)}"
        except httpx.TimeoutException as e:
            last_error = f"Timeout: {str(e)}"
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"

        if not success:
            logger.error(
                f"❌ Webhook send failed (event_id={event_id}, "
                f"attempt={attempts}): {last_error}"
            )

        # Update DB
        new_status = "SENT" if success else "FAILED"
        await db.execute(
            text("""
                UPDATE webhook_events
                SET status = :status, attempts = :attempts, last_error = :last_error
                WHERE id = :id
            """),
            {
                "id": event_id,
                "status": new_status,
                "attempts": attempts,
                "last_error": last_error,
            },
        )
        await db.commit()
        return success

    async def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


webhook_service = WebhookService()
