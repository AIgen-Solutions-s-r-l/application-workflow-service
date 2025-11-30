"""
APScheduler setup and configuration.

Provides background job scheduling with MongoDB persistence.
"""

from typing import Any

from app.core.config import settings
from app.log.logging import logger

# Try to import APScheduler, but don't fail if not installed
try:
    from apscheduler.executors.asyncio import AsyncIOExecutor
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    AsyncIOScheduler = None
    logger.warning("APScheduler not installed, scheduler features disabled")

# Global scheduler instance
_scheduler = None


def create_scheduler():
    """
    Create and configure the APScheduler instance.

    Uses memory jobstore for simplicity (MongoDB jobstore requires
    additional setup with motor).
    """
    global _scheduler

    if not APSCHEDULER_AVAILABLE:
        logger.warning("Cannot create scheduler - APScheduler not installed")
        return None

    if _scheduler is not None:
        return _scheduler

    jobstores = {
        "default": MemoryJobStore(),
    }

    executors = {
        "default": AsyncIOExecutor(),
    }

    job_defaults = {
        "coalesce": True,  # Combine missed runs into one
        "max_instances": 1,  # Prevent overlapping executions
        "misfire_grace_time": 3600,  # 1 hour grace period for misfires
    }

    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone="UTC",
    )

    logger.info("Scheduler created", event_type="scheduler_created")

    return _scheduler


def get_scheduler():
    """Get the global scheduler instance."""
    return _scheduler


def register_jobs(scheduler) -> None:
    """
    Register all scheduled jobs.

    Jobs are only registered if scheduler is enabled in settings.
    """
    if not settings.scheduler_enabled or scheduler is None:
        logger.info("Scheduler disabled, skipping job registration")
        return

    from app.scheduler.jobs.cleanup import (
        cleanup_expired_idempotency,
        cleanup_old_applications,
        cleanup_old_webhook_deliveries,
    )
    from app.scheduler.jobs.monitoring import (
        deep_health_check,
        dlq_alert_check,
    )

    # Cleanup jobs
    scheduler.add_job(
        cleanup_old_applications,
        "cron",
        hour=2,
        minute=0,
        id="cleanup_old_applications",
        name="Cleanup old applications",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_expired_idempotency,
        "interval",
        hours=1,
        id="cleanup_expired_idempotency",
        name="Cleanup expired idempotency keys",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_old_webhook_deliveries,
        "cron",
        hour=3,
        minute=0,
        id="cleanup_old_webhook_deliveries",
        name="Cleanup old webhook deliveries",
        replace_existing=True,
    )

    # Monitoring jobs
    scheduler.add_job(
        deep_health_check,
        "interval",
        minutes=5,
        id="deep_health_check",
        name="Deep health check",
        replace_existing=True,
    )

    scheduler.add_job(
        dlq_alert_check,
        "interval",
        minutes=10,
        id="dlq_alert_check",
        name="DLQ alert check",
        replace_existing=True,
    )

    job_count = len(scheduler.get_jobs())
    logger.info(
        f"Registered {job_count} scheduled jobs",
        event_type="scheduler_jobs_registered",
        job_count=job_count,
    )


async def start_scheduler() -> None:
    """Start the scheduler if enabled."""
    global _scheduler

    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled, not starting")
        return

    if _scheduler is None:
        _scheduler = create_scheduler()
        register_jobs(_scheduler)

    if not _scheduler.running:
        _scheduler.start()
        logger.info("Scheduler started", event_type="scheduler_started")


async def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped", event_type="scheduler_stopped")


def get_job_info(job_id: str) -> dict[str, Any] | None:
    """Get information about a specific job."""
    if _scheduler is None:
        return None

    job = _scheduler.get_job(job_id)
    if job is None:
        return None

    return {
        "id": job.id,
        "name": job.name,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        "trigger": str(job.trigger),
        "pending": job.pending,
    }


def get_all_jobs() -> list[dict[str, Any]]:
    """Get information about all scheduled jobs."""
    if _scheduler is None:
        return []

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
            "pending": job.pending,
        })

    return jobs


def pause_job(job_id: str) -> bool:
    """Pause a scheduled job."""
    if _scheduler is None:
        return False

    try:
        _scheduler.pause_job(job_id)
        logger.info(f"Job paused: {job_id}", event_type="scheduler_job_paused", job_id=job_id)
        return True
    except Exception as e:
        logger.error(f"Failed to pause job {job_id}: {e}")
        return False


def resume_job(job_id: str) -> bool:
    """Resume a paused job."""
    if _scheduler is None:
        return False

    try:
        _scheduler.resume_job(job_id)
        logger.info(f"Job resumed: {job_id}", event_type="scheduler_job_resumed", job_id=job_id)
        return True
    except Exception as e:
        logger.error(f"Failed to resume job {job_id}: {e}")
        return False


def run_job_now(job_id: str) -> bool:
    """Trigger immediate execution of a job."""
    if _scheduler is None:
        return False

    try:
        from datetime import datetime

        _scheduler.modify_job(job_id, next_run_time=datetime.utcnow())
        logger.info(
            f"Job triggered for immediate execution: {job_id}",
            event_type="scheduler_job_triggered",
            job_id=job_id,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to trigger job {job_id}: {e}")
        return False
