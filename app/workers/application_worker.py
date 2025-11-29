"""
Application Worker for processing job applications asynchronously.

This worker consumes messages from the application processing queue,
processes each application, and updates its status accordingly.
"""
import asyncio
import json
import signal

import aio_pika

from app.core.config import settings
from app.core.mongo import applications_collection
from app.core.rabbitmq_client import AsyncRabbitMQClient
from app.core.retry import (
    MaxRetriesExceededError,
    NonRetryableError,
    RetryableError,
    RetryContext,
    retry_with_backoff,
)
from app.log.logging import logger
from app.models.application import ApplicationStatus
from app.services.application_uploader_service import ApplicationUploaderService
from app.services.queue_service import application_queue_service


class ApplicationWorker:
    """
    Worker that processes job applications from RabbitMQ queue.

    Features:
    - Consumes from application_processing_queue
    - Updates application status during processing
    - Implements retry with exponential backoff
    - Moves failed applications to DLQ after max retries
    """

    def __init__(self):
        self._client: AsyncRabbitMQClient | None = None
        self._uploader = ApplicationUploaderService()
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def _get_client(self) -> AsyncRabbitMQClient:
        """Get or create the RabbitMQ client."""
        if self._client is None:
            self._client = AsyncRabbitMQClient(settings.rabbitmq_url)
            await self._client.connect()
        return self._client

    async def process_application(
        self,
        application_id: str,
        user_id: str,
        cv_id: str | None = None,  # noqa: ARG002
        style: str | None = None,  # noqa: ARG002
    ) -> None:
        """
        Process a single application.

        This is where the actual application processing logic goes.
        Currently a placeholder for the processing pipeline.

        Args:
            application_id: The application ID to process.
            user_id: The ID of the user.
            cv_id: Optional CV document ID.
            style: Optional resume style preference.

        Raises:
            RetryableError: For transient failures that can be retried.
            NonRetryableError: For permanent failures.
        """
        from bson import ObjectId

        logger.info(
            "Processing application {application_id}",
            application_id=application_id,
            user_id=user_id,
            event_type="application_processing_start"
        )

        # Update status to PROCESSING
        await self._uploader.update_application_status(
            application_id=application_id,
            status=ApplicationStatus.PROCESSING
        )

        try:
            # Fetch the application document
            doc = await applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )

            if not doc:
                raise NonRetryableError(f"Application {application_id} not found")

            jobs = doc.get("jobs", [])

            # TODO: Implement actual processing logic here
            # This is where you would:
            # 1. Generate/optimize resumes for each job
            # 2. Generate cover letters
            # 3. Submit applications to portals
            # 4. Update job statuses

            # For now, simulate processing
            logger.info(
                "Processing {job_count} jobs for application {application_id}",
                job_count=len(jobs),
                application_id=application_id,
                event_type="jobs_processing"
            )

            # Mark as successful
            await self._uploader.update_application_status(
                application_id=application_id,
                status=ApplicationStatus.SUCCESS
            )

            logger.info(
                "Application {application_id} processed successfully",
                application_id=application_id,
                event_type="application_processing_complete"
            )

        except NonRetryableError:
            raise
        except Exception as e:
            # Classify the error
            if self._is_retryable_error(e):
                raise RetryableError(str(e)) from e
            else:
                raise NonRetryableError(str(e)) from e

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            error: The exception to check.

        Returns:
            True if the error can be retried, False otherwise.
        """
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "temporarily unavailable",
            "rate limit",
            "too many requests",
            "503",
            "504",
            "502"
        ]

        error_str = str(error).lower()
        return any(pattern in error_str for pattern in retryable_patterns)

    async def handle_message(self, message: aio_pika.IncomingMessage) -> None:
        """
        Handle an incoming message from the queue.

        Args:
            message: The incoming RabbitMQ message.
        """
        try:
            body = json.loads(message.body.decode())
            application_id = body.get("application_id")
            user_id = body.get("user_id")
            cv_id = body.get("cv_id")
            style = body.get("style")

            if not application_id or not user_id:
                logger.error(
                    "Invalid message: missing required fields",
                    body=body,
                    event_type="invalid_message"
                )
                await message.reject(requeue=False)
                return

            logger.info(
                "Received message for application {application_id}",
                application_id=application_id,
                event_type="message_received"
            )

            # Process with retry
            async with RetryContext(application_id) as ctx:
                try:
                    await retry_with_backoff(
                        self.process_application,
                        application_id,
                        user_id,
                        cv_id=cv_id,
                        style=style,
                        max_retries=settings.max_retries,
                        retryable_exceptions=(RetryableError,),
                        on_retry=lambda _attempt, err: ctx.record_error(err)
                    )
                    await message.ack()

                except NonRetryableError as e:
                    logger.error(
                        "Non-retryable error for application {application_id}: {error}",
                        application_id=application_id,
                        error=str(e),
                        event_type="non_retryable_error"
                    )
                    await self._uploader.update_application_status(
                        application_id=application_id,
                        status=ApplicationStatus.FAILED,
                        error_reason=str(e)
                    )
                    await message.ack()

                except MaxRetriesExceededError as e:
                    logger.error(
                        "Max retries exceeded for application {application_id}",
                        application_id=application_id,
                        attempts=e.attempts,
                        error=str(e.last_error),
                        event_type="max_retries_exceeded"
                    )
                    await self._uploader.update_application_status(
                        application_id=application_id,
                        status=ApplicationStatus.FAILED,
                        error_reason=f"Max retries exceeded: {str(e.last_error)}"
                    )
                    # Publish to DLQ
                    await application_queue_service.publish_to_dlq(
                        application_id=application_id,
                        error_message=str(e.last_error),
                        original_message=body
                    )
                    await message.ack()

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to decode message: {error}",
                error=str(e),
                event_type="message_decode_error"
            )
            await message.reject(requeue=False)

        except Exception as e:
            logger.exception(
                "Unexpected error processing message: {error}",
                error=str(e),
                event_type="message_processing_error"
            )
            await message.reject(requeue=True)

    async def start(self) -> None:
        """Start the worker to consume messages."""
        self._running = True
        logger.info(
            "Starting ApplicationWorker",
            queue=settings.application_processing_queue,
            event_type="worker_start"
        )

        try:
            client = await self._get_client()

            # Ensure queue exists with durability
            queue = await client.channel.declare_queue(
                settings.application_processing_queue,
                durable=True
            )

            # Also ensure DLQ exists
            await client.channel.declare_queue(
                settings.application_dlq,
                durable=True
            )

            logger.info(
                "ApplicationWorker connected and consuming from {queue}",
                queue=settings.application_processing_queue,
                event_type="worker_consuming"
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self._running:
                        break
                    await self.handle_message(message)

        except Exception as e:
            logger.error(
                "ApplicationWorker error: {error}",
                error=str(e),
                event_type="worker_error"
            )
            raise

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info(
            "Stopping ApplicationWorker",
            event_type="worker_stop"
        )
        self._running = False
        self._shutdown_event.set()

        if self._client:
            await self._client.close()
            self._client = None


async def run_worker():
    """Run the application worker as a standalone process."""
    worker = ApplicationWorker()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal", event_type="shutdown_signal")
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await worker.start()
    except asyncio.CancelledError:
        logger.info("Worker cancelled", event_type="worker_cancelled")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(run_worker())
