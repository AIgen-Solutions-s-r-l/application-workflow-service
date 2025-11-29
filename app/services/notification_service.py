"""
Notification service for publishing application events to RabbitMQ.

This module provides enriched notification payloads for downstream consumers,
replacing the basic {"updated": true} format with structured event data.
"""
from datetime import datetime
from typing import Optional

from app.log.logging import logger
from app.services.base_publisher import BasePublisher
from app.core.config import settings


class NotificationPublisher(BasePublisher):
    """
    Publisher for application-related notifications.

    Publishes structured event payloads to the middleware notification queue
    for consumption by downstream services.
    """

    # Schema version for backward compatibility tracking
    SCHEMA_VERSION = "1.0"

    def get_queue_name(self) -> str:
        return settings.middleware_queue

    async def publish_application_submitted(
        self,
        application_id: str,
        user_id: str,
        job_count: int
    ) -> None:
        """
        Publish notification when a new application is submitted.

        Args:
            application_id: The ID of the submitted application.
            user_id: The ID of the user who submitted.
            job_count: Number of jobs in the application.
        """
        payload = self._build_event_payload(
            event="application.submitted",
            application_id=application_id,
            user_id=user_id,
            status="pending",
            job_count=job_count
        )

        logger.info(
            "Publishing application.submitted event",
            event_type="notification_publishing",
            application_id=application_id,
            user_id=user_id
        )

        await self.publish(payload, persistent=True)

    async def publish_status_changed(
        self,
        application_id: str,
        user_id: str,
        status: str,
        job_count: int,
        previous_status: Optional[str] = None,
        error_reason: Optional[str] = None
    ) -> None:
        """
        Publish notification when application status changes.

        Args:
            application_id: The ID of the application.
            user_id: The ID of the user.
            status: The new status.
            job_count: Number of jobs in the application.
            previous_status: The previous status (if known).
            error_reason: Error message if status is 'failed'.
        """
        payload = self._build_event_payload(
            event="application.status_changed",
            application_id=application_id,
            user_id=user_id,
            status=status,
            job_count=job_count,
            previous_status=previous_status,
            error_reason=error_reason
        )

        logger.info(
            "Publishing application.status_changed event",
            event_type="notification_publishing",
            application_id=application_id,
            user_id=user_id,
            status=status
        )

        await self.publish(payload, persistent=True)

    async def publish_application_updated(self) -> None:
        """
        Publishes a legacy notification about application update.

        DEPRECATED: Use publish_application_submitted or publish_status_changed instead.
        Kept for backward compatibility with existing consumers.
        """
        logger.warning(
            "Using deprecated publish_application_updated method",
            event_type="notification_publishing"
        )

        # Send both legacy and new format for backward compatibility
        legacy_payload = {"updated": True}
        await self.publish(legacy_payload, persistent=False)

    def _build_event_payload(
        self,
        event: str,
        application_id: str,
        user_id: str,
        status: str,
        job_count: int,
        previous_status: Optional[str] = None,
        error_reason: Optional[str] = None
    ) -> dict:
        """
        Build a standardized event payload.

        Args:
            event: Event type (e.g., 'application.submitted', 'application.status_changed').
            application_id: The application ID.
            user_id: The user ID.
            status: Current status.
            job_count: Number of jobs.
            previous_status: Previous status (optional).
            error_reason: Error message (optional).

        Returns:
            Structured event payload dict.
        """
        payload = {
            "event": event,
            "version": self.SCHEMA_VERSION,
            "application_id": application_id,
            "user_id": user_id,
            "status": status,
            "job_count": job_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if previous_status:
            payload["previous_status"] = previous_status

        if error_reason:
            payload["error_reason"] = error_reason

        return payload
