"""
Queue service for publishing applications to the processing queue.

This module handles publishing application data to RabbitMQ for
asynchronous processing by the ApplicationWorker.
"""
import json
from typing import Optional

from app.core.config import settings
from app.core.rabbitmq_client import AsyncRabbitMQClient
from app.log.logging import logger


class ApplicationQueueService:
    """
    Service for publishing applications to the processing queue.
    """

    def __init__(self):
        self._client: Optional[AsyncRabbitMQClient] = None

    async def _get_client(self) -> AsyncRabbitMQClient:
        """Get or create the RabbitMQ client."""
        if self._client is None:
            self._client = AsyncRabbitMQClient(settings.rabbitmq_url)
            await self._client.connect()
        return self._client

    async def publish_application_for_processing(
        self,
        application_id: str,
        user_id: str,
        job_count: int,
        cv_id: Optional[str] = None,
        style: Optional[str] = None
    ) -> bool:
        """
        Publish an application to the processing queue.

        Args:
            application_id: The application ID to process.
            user_id: The ID of the user who submitted the application.
            job_count: Number of jobs in the application.
            cv_id: Optional CV document ID.
            style: Optional resume style preference.

        Returns:
            True if published successfully, False otherwise.
        """
        if not settings.async_processing_enabled:
            logger.debug(
                "Async processing disabled, skipping queue publish for {application_id}",
                application_id=application_id,
                event_type="async_processing_disabled"
            )
            return False

        try:
            client = await self._get_client()

            message = {
                "application_id": application_id,
                "user_id": user_id,
                "job_count": job_count,
                "cv_id": cv_id,
                "style": style
            }

            await client.publish_message(
                queue_name=settings.application_processing_queue,
                message=message,
                persistent=True
            )

            logger.info(
                "Application {application_id} published to processing queue",
                application_id=application_id,
                user_id=user_id,
                job_count=job_count,
                event_type="application_queued"
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to publish application {application_id} to queue: {error}",
                application_id=application_id,
                error=str(e),
                event_type="queue_publish_failed"
            )
            return False

    async def publish_to_dlq(
        self,
        application_id: str,
        error_message: str,
        original_message: dict
    ) -> bool:
        """
        Publish a failed message to the dead letter queue.

        Args:
            application_id: The application ID that failed.
            error_message: Description of the failure.
            original_message: The original message that failed processing.

        Returns:
            True if published successfully, False otherwise.
        """
        try:
            client = await self._get_client()

            dlq_message = {
                "application_id": application_id,
                "error_message": error_message,
                "original_message": original_message,
                "failed_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"
            }

            await client.publish_message(
                queue_name=settings.application_dlq,
                message=dlq_message,
                persistent=True
            )

            logger.warning(
                "Application {application_id} published to DLQ",
                application_id=application_id,
                error=error_message,
                event_type="application_dlq"
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to publish to DLQ for {application_id}: {error}",
                application_id=application_id,
                error=str(e),
                event_type="dlq_publish_failed"
            )
            return False

    async def close(self):
        """Close the RabbitMQ connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Global instance
application_queue_service = ApplicationQueueService()
