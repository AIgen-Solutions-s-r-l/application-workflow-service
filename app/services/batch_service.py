"""
Batch operations service for handling multiple applications.

Provides:
- Batch submission of multiple job applications
- Batch status tracking
- Background batch processing
"""

import asyncio
from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel

from app.core.websocket_manager import ws_manager
from app.log.logging import logger
from app.services.application_uploader_service import ApplicationUploaderService
from app.services.notification_service import NotificationPublisher


class BatchStatus(str, Enum):
    """Batch processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"  # Some succeeded, some failed
    FAILED = "failed"


class BatchItem(BaseModel):
    """A single item in a batch submission."""

    jobs: list[dict]
    style: str | None = None


class BatchResult(BaseModel):
    """Result of a single batch item processing."""

    index: int
    application_id: str | None = None
    status: str
    error: str | None = None


class BatchResponse(BaseModel):
    """Response for batch submission."""

    batch_id: str
    status: BatchStatus
    total: int
    results: list[BatchResult] = []
    created_at: datetime


class BatchStatusResponse(BaseModel):
    """Response for batch status query."""

    batch_id: str
    status: BatchStatus
    total: int
    processed: int
    succeeded: int
    failed: int
    results: list[BatchResult]
    created_at: datetime
    completed_at: datetime | None = None


# In-memory batch tracking (consider moving to Redis for production)
_batch_store: dict[str, dict] = {}


class BatchService:
    """
    Service for batch application operations.
    """

    def __init__(self):
        self._uploader = ApplicationUploaderService()
        self._notification = NotificationPublisher()

    async def create_batch(
        self, user_id: str, items: list[BatchItem], cv_id: str | None = None
    ) -> BatchResponse:
        """
        Create and start processing a batch of applications.

        Args:
            user_id: The user ID submitting the batch.
            items: List of batch items to process.
            cv_id: Optional shared CV ID for all applications.

        Returns:
            BatchResponse with batch ID and initial status.
        """
        batch_id = str(uuid4())
        now = datetime.utcnow()

        # Initialize batch tracking
        _batch_store[batch_id] = {
            "user_id": user_id,
            "status": BatchStatus.PENDING,
            "total": len(items),
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "results": [],
            "created_at": now,
            "completed_at": None,
        }

        # Start background processing
        asyncio.create_task(self._process_batch(batch_id, user_id, items, cv_id))

        return BatchResponse(
            batch_id=batch_id, status=BatchStatus.PENDING, total=len(items), created_at=now
        )

    async def _process_batch(
        self, batch_id: str, user_id: str, items: list[BatchItem], cv_id: str | None
    ) -> None:
        """
        Process batch items in background.

        Args:
            batch_id: The batch ID.
            user_id: The user ID.
            items: Items to process.
            cv_id: Optional shared CV ID.
        """
        batch_data = _batch_store.get(batch_id)
        if not batch_data:
            return

        batch_data["status"] = BatchStatus.PROCESSING

        # Notify via WebSocket
        await ws_manager.send_batch_update(
            user_id=user_id,
            batch_id=batch_id,
            status=BatchStatus.PROCESSING.value,
            total=len(items),
            processed=0,
            failed=0,
        )

        for index, item in enumerate(items):
            result = BatchResult(index=index, status="pending")

            try:
                # Create application
                application_id = await self._uploader.insert_application_jobs(
                    user_id=user_id, job_list_to_apply=item.jobs, cv_id=cv_id, style=item.style
                )

                if application_id:
                    result.application_id = application_id
                    result.status = "submitted"
                    batch_data["succeeded"] += 1
                else:
                    result.status = "failed"
                    result.error = "Failed to create application"
                    batch_data["failed"] += 1

            except Exception as e:
                logger.error(f"Batch item {index} failed: {e}")
                result.status = "failed"
                result.error = str(e)
                batch_data["failed"] += 1

            batch_data["results"].append(result)
            batch_data["processed"] += 1

            # Notify progress via WebSocket
            await ws_manager.send_batch_update(
                user_id=user_id,
                batch_id=batch_id,
                status=BatchStatus.PROCESSING.value,
                total=len(items),
                processed=batch_data["processed"],
                failed=batch_data["failed"],
            )

            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)

        # Determine final status
        if batch_data["failed"] == 0:
            batch_data["status"] = BatchStatus.COMPLETED
        elif batch_data["succeeded"] == 0:
            batch_data["status"] = BatchStatus.FAILED
        else:
            batch_data["status"] = BatchStatus.PARTIAL

        batch_data["completed_at"] = datetime.utcnow()

        # Final WebSocket notification
        await ws_manager.send_batch_update(
            user_id=user_id,
            batch_id=batch_id,
            status=batch_data["status"].value,
            total=len(items),
            processed=batch_data["processed"],
            failed=batch_data["failed"],
        )

        logger.info(
            f"Batch {batch_id} completed: "
            f"{batch_data['succeeded']} succeeded, {batch_data['failed']} failed"
        )

    async def get_batch_status(self, batch_id: str, user_id: str) -> BatchStatusResponse | None:
        """
        Get the status of a batch.

        Args:
            batch_id: The batch ID to query.
            user_id: The user ID (for authorization).

        Returns:
            BatchStatusResponse or None if not found.
        """
        batch_data = _batch_store.get(batch_id)

        if not batch_data:
            return None

        # Check ownership
        if batch_data["user_id"] != user_id:
            return None

        return BatchStatusResponse(
            batch_id=batch_id,
            status=batch_data["status"],
            total=batch_data["total"],
            processed=batch_data["processed"],
            succeeded=batch_data["succeeded"],
            failed=batch_data["failed"],
            results=batch_data["results"],
            created_at=batch_data["created_at"],
            completed_at=batch_data["completed_at"],
        )

    async def cancel_batch(self, batch_id: str, user_id: str) -> bool:
        """
        Cancel a pending or processing batch.

        Args:
            batch_id: The batch ID to cancel.
            user_id: The user ID (for authorization).

        Returns:
            True if cancelled, False otherwise.
        """
        batch_data = _batch_store.get(batch_id)

        if not batch_data:
            return False

        if batch_data["user_id"] != user_id:
            return False

        if batch_data["status"] not in (BatchStatus.PENDING, BatchStatus.PROCESSING):
            return False

        batch_data["status"] = BatchStatus.FAILED
        batch_data["completed_at"] = datetime.utcnow()

        return True


# Global service instance
batch_service = BatchService()
