"""
Webhook service for managing webhook registrations and deliveries.

Provides:
- CRUD operations for webhooks
- Event dispatching to webhooks
- Delivery management with retries
- HMAC signature generation
"""

import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings
from app.core.metrics import (
    record_webhook_auto_disabled,
    record_webhook_delivery,
    record_webhook_retry,
)
from app.core.mongo import webhook_deliveries_collection, webhooks_collection
from app.log.logging import logger
from app.models.webhook import (
    DeliveryStatus,
    Webhook,
    WebhookCreate,
    WebhookDelivery,
    WebhookEventType,
    WebhookPayload,
    WebhookStatus,
    WebhookUpdate,
)

# Retry delays in seconds: 1m, 5m, 15m, 1h, 4h
RETRY_DELAYS = [60, 300, 900, 3600, 14400]


class WebhookService:
    """Service for webhook management and delivery."""

    def __init__(self):
        self.webhooks = webhooks_collection
        self.deliveries = webhook_deliveries_collection

    # =========================================================================
    # Webhook CRUD Operations
    # =========================================================================

    async def create_webhook(
        self, user_id: str, webhook_data: WebhookCreate
    ) -> Webhook:
        """
        Create a new webhook registration.

        Args:
            user_id: Owner user ID.
            webhook_data: Webhook configuration.

        Returns:
            Created webhook with secret.

        Raises:
            ValueError: If user has reached webhook limit or URL is invalid.
        """
        # Check webhook limit per user
        count = await self.webhooks.count_documents({"user_id": user_id})
        if count >= settings.webhook_max_per_user:
            raise ValueError(
                f"Maximum webhooks ({settings.webhook_max_per_user}) reached"
            )

        # Validate HTTPS requirement
        url = str(webhook_data.url)
        if settings.webhook_require_https and not url.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")

        # Generate webhook ID and secret
        webhook_id = f"wh_{secrets.token_hex(12)}"
        secret = secrets.token_urlsafe(32)

        now = datetime.utcnow()
        webhook = Webhook(
            id=webhook_id,
            user_id=user_id,
            url=url,
            secret=secret,
            name=webhook_data.name,
            description=webhook_data.description,
            events=webhook_data.events,
            status=WebhookStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        await self.webhooks.insert_one(webhook.model_dump())

        logger.info(
            "Webhook created",
            event_type="webhook_created",
            webhook_id=webhook_id,
            user_id=user_id,
            events=[e.value for e in webhook_data.events],
        )

        return webhook

    async def get_webhook(self, webhook_id: str, user_id: str) -> Webhook | None:
        """Get a webhook by ID for a specific user."""
        doc = await self.webhooks.find_one(
            {"id": webhook_id, "user_id": user_id}
        )
        if doc:
            return Webhook(**doc)
        return None

    async def list_webhooks(
        self, user_id: str, include_disabled: bool = False
    ) -> list[Webhook]:
        """List all webhooks for a user."""
        query = {"user_id": user_id}
        if not include_disabled:
            query["status"] = {"$ne": WebhookStatus.DISABLED.value}

        cursor = self.webhooks.find(query).sort("created_at", -1)
        webhooks = []
        async for doc in cursor:
            webhooks.append(Webhook(**doc))
        return webhooks

    async def update_webhook(
        self, webhook_id: str, user_id: str, updates: WebhookUpdate
    ) -> Webhook | None:
        """Update a webhook."""
        # Build update dict excluding None values
        update_data = {
            k: v for k, v in updates.model_dump().items() if v is not None
        }

        if not update_data:
            return await self.get_webhook(webhook_id, user_id)

        # Validate HTTPS if URL is being updated
        if "url" in update_data:
            url = str(update_data["url"])
            if settings.webhook_require_https and not url.startswith("https://"):
                raise ValueError("Webhook URL must use HTTPS")

        update_data["updated_at"] = datetime.utcnow()

        # Reset consecutive failures if re-activating
        if update_data.get("status") == WebhookStatus.ACTIVE.value:
            update_data["consecutive_failures"] = 0
            update_data["last_error"] = None

        result = await self.webhooks.find_one_and_update(
            {"id": webhook_id, "user_id": user_id},
            {"$set": update_data},
            return_document=True,
        )

        if result:
            logger.info(
                "Webhook updated",
                event_type="webhook_updated",
                webhook_id=webhook_id,
                user_id=user_id,
                updates=list(update_data.keys()),
            )
            return Webhook(**result)

        return None

    async def delete_webhook(self, webhook_id: str, user_id: str) -> bool:
        """Delete a webhook and its delivery history."""
        result = await self.webhooks.delete_one(
            {"id": webhook_id, "user_id": user_id}
        )

        if result.deleted_count > 0:
            # Also delete delivery history
            await self.deliveries.delete_many({"webhook_id": webhook_id})

            logger.info(
                "Webhook deleted",
                event_type="webhook_deleted",
                webhook_id=webhook_id,
                user_id=user_id,
            )
            return True

        return False

    async def rotate_secret(self, webhook_id: str, user_id: str) -> str | None:
        """Generate a new secret for a webhook."""
        new_secret = secrets.token_urlsafe(32)

        result = await self.webhooks.find_one_and_update(
            {"id": webhook_id, "user_id": user_id},
            {
                "$set": {
                    "secret": new_secret,
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True,
        )

        if result:
            logger.info(
                "Webhook secret rotated",
                event_type="webhook_secret_rotated",
                webhook_id=webhook_id,
                user_id=user_id,
            )
            return new_secret

        return None

    # =========================================================================
    # Event Dispatching
    # =========================================================================

    async def dispatch_event(
        self,
        event_type: WebhookEventType,
        user_id: str,
        payload: dict[str, Any],
    ) -> list[str]:
        """
        Dispatch an event to all matching webhooks.

        Args:
            event_type: Type of event.
            user_id: User ID to find webhooks for.
            payload: Event payload data.

        Returns:
            List of created delivery IDs.
        """
        if not settings.webhooks_enabled:
            return []

        # Find active webhooks subscribed to this event
        webhooks = await self._get_matching_webhooks(user_id, event_type)

        if not webhooks:
            return []

        delivery_ids = []
        for webhook in webhooks:
            delivery_id = await self._create_delivery(webhook, event_type, payload)
            delivery_ids.append(delivery_id)

        logger.info(
            "Event dispatched to webhooks",
            event_type="webhook_event_dispatched",
            webhook_event=event_type.value,
            user_id=user_id,
            webhook_count=len(webhooks),
        )

        return delivery_ids

    async def _get_matching_webhooks(
        self, user_id: str, event_type: WebhookEventType
    ) -> list[Webhook]:
        """Get active webhooks for a user that subscribe to an event."""
        cursor = self.webhooks.find({
            "user_id": user_id,
            "status": WebhookStatus.ACTIVE.value,
            "events": event_type.value,
        })

        webhooks = []
        async for doc in cursor:
            webhooks.append(Webhook(**doc))
        return webhooks

    async def _create_delivery(
        self,
        webhook: Webhook,
        event_type: WebhookEventType,
        payload: dict[str, Any],
    ) -> str:
        """Create a delivery record for a webhook."""
        delivery_id = f"del_{secrets.token_hex(12)}"
        now = datetime.utcnow()

        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook.id,
            user_id=webhook.user_id,
            event_type=event_type,
            payload=payload,
            status=DeliveryStatus.PENDING,
            attempts=0,
            max_attempts=settings.webhook_max_retries,
            created_at=now,
            next_retry_at=now,  # Ready for immediate delivery
        )

        await self.deliveries.insert_one(delivery.model_dump())

        return delivery_id

    # =========================================================================
    # Delivery Execution
    # =========================================================================

    async def deliver(self, delivery_id: str) -> bool:
        """
        Attempt to deliver a webhook.

        Args:
            delivery_id: Delivery record ID.

        Returns:
            True if delivery succeeded.
        """
        # Get delivery record
        delivery_doc = await self.deliveries.find_one({"id": delivery_id})
        if not delivery_doc:
            logger.warning(f"Delivery not found: {delivery_id}")
            return False

        delivery = WebhookDelivery(**delivery_doc)

        # Check if already delivered or permanently failed
        if delivery.status in (
            DeliveryStatus.DELIVERED,
            DeliveryStatus.PERMANENTLY_FAILED,
        ):
            return delivery.status == DeliveryStatus.DELIVERED

        # Get webhook
        webhook_doc = await self.webhooks.find_one({"id": delivery.webhook_id})
        if not webhook_doc:
            await self._mark_permanently_failed(delivery, "Webhook deleted")
            return False

        webhook = Webhook(**webhook_doc)

        # Check if webhook is disabled
        if webhook.status == WebhookStatus.DISABLED:
            await self._mark_permanently_failed(delivery, "Webhook disabled")
            return False

        # Build payload
        webhook_payload = WebhookPayload(
            id=delivery.id,
            event=delivery.event_type,
            created_at=delivery.created_at.isoformat() + "Z",
            data=delivery.payload,
        )

        body = webhook_payload.model_dump()

        # Sign payload
        signature = self._sign_payload(body, webhook.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": delivery.event_type.value,
            "X-Webhook-Delivery": delivery.id,
            "User-Agent": "ApplicationManager-Webhook/1.0",
        }

        # Attempt delivery
        start_time = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=settings.webhook_timeout_seconds
            ) as client:
                response = await client.post(
                    webhook.url,
                    json=body,
                    headers=headers,
                )

            duration_ms = int((time.time() - start_time) * 1000)

            if response.status_code < 300:
                await self._mark_delivered(
                    delivery, webhook, response.status_code, duration_ms
                )
                return True
            else:
                await self._mark_failed(
                    delivery,
                    webhook,
                    f"HTTP {response.status_code}",
                    response.status_code,
                    response.text[:1000] if response.text else None,
                    duration_ms,
                )
                return False

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            await self._mark_failed(
                delivery, webhook, "Request timeout", duration_ms=duration_ms
            )
            return False

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            await self._mark_failed(
                delivery, webhook, str(e), duration_ms=duration_ms
            )
            return False

    def _sign_payload(self, payload: dict, secret: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        message = json.dumps(payload, sort_keys=True, default=str)
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={signature}"

    async def _mark_delivered(
        self,
        delivery: WebhookDelivery,
        webhook: Webhook,
        status_code: int,
        duration_ms: int,
    ) -> None:
        """Mark delivery as successful."""
        now = datetime.utcnow()

        await self.deliveries.update_one(
            {"id": delivery.id},
            {
                "$set": {
                    "status": DeliveryStatus.DELIVERED.value,
                    "delivered_at": now,
                    "response_status": status_code,
                    "duration_ms": duration_ms,
                },
                "$inc": {"attempts": 1},
            },
        )

        # Update webhook stats
        await self.webhooks.update_one(
            {"id": webhook.id},
            {
                "$set": {
                    "last_delivery_at": now,
                    "last_success_at": now,
                    "consecutive_failures": 0,
                    "last_error": None,
                },
                "$inc": {
                    "total_deliveries": 1,
                    "successful_deliveries": 1,
                },
            },
        )

        # Record metrics
        record_webhook_delivery(
            delivery.event_type.value, "success", duration_ms / 1000.0
        )

        logger.info(
            "Webhook delivered",
            event_type="webhook_delivered",
            delivery_id=delivery.id,
            webhook_id=webhook.id,
            status_code=status_code,
            duration_ms=duration_ms,
        )

    async def _mark_failed(
        self,
        delivery: WebhookDelivery,
        webhook: Webhook,
        error: str,
        status_code: int | None = None,
        response_body: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Mark delivery as failed and schedule retry."""
        now = datetime.utcnow()
        new_attempts = delivery.attempts + 1

        # Calculate next retry time
        if new_attempts >= delivery.max_attempts:
            # Permanent failure
            await self._mark_permanently_failed(delivery, error)

            # Update webhook stats
            await self._update_webhook_failure(webhook, error)

            # Check auto-disable threshold
            await self._check_auto_disable(webhook)
            return

        # Schedule retry
        retry_delay = RETRY_DELAYS[min(new_attempts - 1, len(RETRY_DELAYS) - 1)]
        next_retry = now + timedelta(seconds=retry_delay)

        await self.deliveries.update_one(
            {"id": delivery.id},
            {
                "$set": {
                    "status": DeliveryStatus.FAILED.value,
                    "next_retry_at": next_retry,
                    "response_status": status_code,
                    "response_body": response_body,
                    "error": error,
                    "duration_ms": duration_ms,
                },
                "$inc": {"attempts": 1},
            },
        )

        # Update webhook stats
        await self._update_webhook_failure(webhook, error)

        # Record metrics
        record_webhook_delivery(
            delivery.event_type.value,
            "failed",
            duration_ms / 1000.0 if duration_ms else None,
        )
        record_webhook_retry(delivery.event_type.value, new_attempts)

        logger.warning(
            "Webhook delivery failed, will retry",
            event_type="webhook_delivery_failed",
            delivery_id=delivery.id,
            webhook_id=webhook.id,
            error=error,
            attempt=new_attempts,
            next_retry=next_retry.isoformat(),
        )

    async def _mark_permanently_failed(
        self, delivery: WebhookDelivery, error: str
    ) -> None:
        """Mark delivery as permanently failed."""
        await self.deliveries.update_one(
            {"id": delivery.id},
            {
                "$set": {
                    "status": DeliveryStatus.PERMANENTLY_FAILED.value,
                    "error": error,
                    "next_retry_at": None,
                },
                "$inc": {"attempts": 1},
            },
        )

        logger.error(
            "Webhook delivery permanently failed",
            event_type="webhook_delivery_permanent_failure",
            delivery_id=delivery.id,
            error=error,
        )

    async def _update_webhook_failure(self, webhook: Webhook, error: str) -> None:
        """Update webhook stats after failure."""
        await self.webhooks.update_one(
            {"id": webhook.id},
            {
                "$set": {
                    "last_delivery_at": datetime.utcnow(),
                    "last_error": error,
                },
                "$inc": {
                    "total_deliveries": 1,
                    "failed_deliveries": 1,
                    "consecutive_failures": 1,
                },
            },
        )

    async def _check_auto_disable(self, webhook: Webhook) -> None:
        """Check if webhook should be auto-disabled due to failures."""
        doc = await self.webhooks.find_one({"id": webhook.id})
        if not doc:
            return

        if doc.get("consecutive_failures", 0) >= settings.webhook_auto_disable_threshold:
            await self.webhooks.update_one(
                {"id": webhook.id},
                {
                    "$set": {
                        "status": WebhookStatus.DISABLED.value,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            # Record metrics
            record_webhook_auto_disabled()

            logger.warning(
                "Webhook auto-disabled due to consecutive failures",
                event_type="webhook_auto_disabled",
                webhook_id=webhook.id,
                consecutive_failures=doc.get("consecutive_failures"),
            )

    # =========================================================================
    # Delivery Management
    # =========================================================================

    async def get_pending_deliveries(self, limit: int = 100) -> list[WebhookDelivery]:
        """Get deliveries ready for retry."""
        now = datetime.utcnow()

        cursor = self.deliveries.find({
            "status": {"$in": [
                DeliveryStatus.PENDING.value,
                DeliveryStatus.FAILED.value,
            ]},
            "next_retry_at": {"$lte": now},
        }).sort("next_retry_at", 1).limit(limit)

        deliveries = []
        async for doc in cursor:
            deliveries.append(WebhookDelivery(**doc))
        return deliveries

    async def list_deliveries(
        self,
        webhook_id: str,
        user_id: str,
        limit: int = 50,
    ) -> list[WebhookDelivery]:
        """List recent deliveries for a webhook."""
        cursor = self.deliveries.find({
            "webhook_id": webhook_id,
            "user_id": user_id,
        }).sort("created_at", -1).limit(limit)

        deliveries = []
        async for doc in cursor:
            deliveries.append(WebhookDelivery(**doc))
        return deliveries

    async def test_webhook(
        self, webhook_id: str, user_id: str
    ) -> tuple[bool, str, int | None, int | None, str | None]:
        """
        Send a test event to a webhook.

        Returns:
            Tuple of (success, delivery_id, status_code, duration_ms, error)
        """
        webhook = await self.get_webhook(webhook_id, user_id)
        if not webhook:
            return False, "", None, None, "Webhook not found"

        # Create test delivery
        test_payload = {
            "test": True,
            "message": "This is a test webhook delivery",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        delivery_id = await self._create_delivery(
            webhook, WebhookEventType.APPLICATION_SUBMITTED, test_payload
        )

        # Attempt delivery
        success = await self.deliver(delivery_id)

        # Get delivery result
        delivery_doc = await self.deliveries.find_one({"id": delivery_id})
        if delivery_doc:
            delivery = WebhookDelivery(**delivery_doc)
            return (
                success,
                delivery_id,
                delivery.response_status,
                delivery.duration_ms,
                delivery.error,
            )

        return success, delivery_id, None, None, None


# Singleton instance
webhook_service = WebhookService()
