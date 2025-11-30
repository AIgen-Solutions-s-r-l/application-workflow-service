"""
Cleanup scheduled jobs.

Jobs for cleaning up old data, expired keys, and maintaining database hygiene.
"""

from datetime import datetime, timedelta

from app.core.config import settings
from app.core.mongo import (
    failed_applications_collection,
    success_applications_collection,
    webhook_deliveries_collection,
)
from app.log.logging import logger
from app.scheduler.history import record_job_execution


async def cleanup_old_applications() -> dict:
    """
    Remove applications older than the retention period.

    Cleans up both successful and failed applications that are
    older than CLEANUP_RETENTION_DAYS (default 90 days).
    """
    job_id = "cleanup_old_applications"
    start_time = datetime.utcnow()

    try:
        retention_days = settings.cleanup_retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        # Clean successful applications
        success_result = await success_applications_collection.delete_many(
            {"created_at": {"$lt": cutoff}}
        )

        # Clean failed applications
        failed_result = await failed_applications_collection.delete_many(
            {"created_at": {"$lt": cutoff}}
        )

        total_deleted = success_result.deleted_count + failed_result.deleted_count

        result = {
            "success_deleted": success_result.deleted_count,
            "failed_deleted": failed_result.deleted_count,
            "total_deleted": total_deleted,
            "cutoff_date": cutoff.isoformat(),
            "retention_days": retention_days,
        }

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(
            f"Cleaned up {total_deleted} old applications",
            event_type="cleanup_old_applications",
            **result,
        )

        await record_job_execution(
            job_id=job_id,
            job_name="Cleanup old applications",
            status="success",
            result=result,
            duration_ms=duration_ms,
        )

        return result

    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.error(
            f"Failed to cleanup old applications: {e}",
            event_type="cleanup_old_applications_failed",
            error=str(e),
        )

        await record_job_execution(
            job_id=job_id,
            job_name="Cleanup old applications",
            status="failed",
            error=str(e),
            duration_ms=duration_ms,
        )

        raise


async def cleanup_expired_idempotency() -> dict:
    """
    Remove expired idempotency keys.

    Idempotency keys have a TTL index, but this job ensures
    any missed expirations are cleaned up.
    """
    job_id = "cleanup_expired_idempotency"
    start_time = datetime.utcnow()

    try:
        from app.core.mongo import database

        idempotency_collection = database["idempotency_keys"]

        # Delete expired keys
        result = await idempotency_collection.delete_many(
            {"expires_at": {"$lt": datetime.utcnow()}}
        )

        cleanup_result = {
            "deleted_count": result.deleted_count,
        }

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(
            f"Cleaned up {result.deleted_count} expired idempotency keys",
            event_type="cleanup_expired_idempotency",
            **cleanup_result,
        )

        await record_job_execution(
            job_id=job_id,
            job_name="Cleanup expired idempotency keys",
            status="success",
            result=cleanup_result,
            duration_ms=duration_ms,
        )

        return cleanup_result

    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.error(
            f"Failed to cleanup idempotency keys: {e}",
            event_type="cleanup_expired_idempotency_failed",
            error=str(e),
        )

        await record_job_execution(
            job_id=job_id,
            job_name="Cleanup expired idempotency keys",
            status="failed",
            error=str(e),
            duration_ms=duration_ms,
        )

        raise


async def cleanup_old_webhook_deliveries() -> dict:
    """
    Remove webhook deliveries older than retention period.

    While deliveries have a TTL index, this ensures cleanup of
    any orphaned or missed records.
    """
    job_id = "cleanup_old_webhook_deliveries"
    start_time = datetime.utcnow()

    try:
        # Keep deliveries for 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)

        result = await webhook_deliveries_collection.delete_many(
            {"created_at": {"$lt": cutoff}}
        )

        cleanup_result = {
            "deleted_count": result.deleted_count,
            "cutoff_date": cutoff.isoformat(),
        }

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(
            f"Cleaned up {result.deleted_count} old webhook deliveries",
            event_type="cleanup_old_webhook_deliveries",
            **cleanup_result,
        )

        await record_job_execution(
            job_id=job_id,
            job_name="Cleanup old webhook deliveries",
            status="success",
            result=cleanup_result,
            duration_ms=duration_ms,
        )

        return cleanup_result

    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.error(
            f"Failed to cleanup webhook deliveries: {e}",
            event_type="cleanup_old_webhook_deliveries_failed",
            error=str(e),
        )

        await record_job_execution(
            job_id=job_id,
            job_name="Cleanup old webhook deliveries",
            status="failed",
            error=str(e),
            duration_ms=duration_ms,
        )

        raise
