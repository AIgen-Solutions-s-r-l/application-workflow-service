"""
Scheduler API router.

Provides endpoints for:
- Listing scheduled jobs
- Viewing job details and history
- Triggering jobs manually
- Pausing/resuming jobs
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.admin_auth import AdminRole, AdminUser, require_admin_role
from app.core.config import settings
from app.log.logging import logger
from app.scheduler.history import get_job_history, get_job_stats
from app.scheduler.scheduler import (
    get_all_jobs,
    get_job_info,
    get_scheduler,
    pause_job,
    resume_job,
    run_job_now,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def check_scheduler_enabled():
    """Dependency to check if scheduler is enabled."""
    if not settings.scheduler_enabled:
        raise HTTPException(
            status_code=503,
            detail="Scheduler is not enabled",
        )


@router.get(
    "/jobs",
    summary="List scheduled jobs",
    description="List all registered scheduled jobs with their next run times.",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def list_jobs(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
):
    """
    List all scheduled jobs.

    Returns:
        List of jobs with ID, name, trigger, and next run time.
    """
    scheduler = get_scheduler()
    if scheduler is None:
        return {"jobs": [], "scheduler_running": False}

    jobs = get_all_jobs()

    return {
        "jobs": jobs,
        "scheduler_running": scheduler.running,
        "job_count": len(jobs),
    }


@router.get(
    "/jobs/{job_id}",
    summary="Get job details",
    description="Get details of a specific job including execution history.",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def get_job_details(
    job_id: str,
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
):
    """
    Get details of a specific job.

    Args:
        job_id: Job ID to look up

    Returns:
        Job details including configuration and recent execution history.
    """
    job = get_job_info(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get execution history
    history = await get_job_history(job_id=job_id, limit=20)

    # Get statistics
    stats = await get_job_stats(job_id)

    return {
        **job,
        "history": history,
        "stats": stats,
    }


@router.get(
    "/jobs/{job_id}/history",
    summary="Get job execution history",
    description="Get execution history for a specific job.",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def get_job_execution_history(
    job_id: str,
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
    status: Annotated[
        str | None,
        Query(description="Filter by status: success, failed, warning"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum results"),
    ] = 50,
):
    """
    Get execution history for a job.

    Args:
        job_id: Job ID
        status: Filter by execution status
        limit: Maximum number of records

    Returns:
        List of execution records.
    """
    history = await get_job_history(job_id=job_id, status=status, limit=limit)

    return {
        "job_id": job_id,
        "history": history,
        "count": len(history),
    }


@router.post(
    "/jobs/{job_id}/run",
    summary="Run job now",
    description="Trigger immediate execution of a scheduled job.",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def trigger_job(
    job_id: str,
    admin: AdminUser = Depends(require_admin_role(AdminRole.OPERATOR)),
):
    """
    Trigger immediate execution of a job.

    Args:
        job_id: Job ID to trigger

    Returns:
        Confirmation message.
    """
    job = get_job_info(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    success = run_job_now(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to trigger job")

    logger.info(
        f"Job triggered manually: {job_id}",
        event_type="scheduler_job_manual_trigger",
        job_id=job_id,
        admin_id=admin.user_id,
    )

    return {
        "message": f"Job {job_id} scheduled for immediate execution",
        "job_id": job_id,
    }


@router.post(
    "/jobs/{job_id}/pause",
    summary="Pause job",
    description="Pause a scheduled job (it won't run until resumed).",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def pause_scheduled_job(
    job_id: str,
    admin: AdminUser = Depends(require_admin_role(AdminRole.OPERATOR)),
):
    """
    Pause a scheduled job.

    Args:
        job_id: Job ID to pause

    Returns:
        Confirmation message.
    """
    job = get_job_info(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    success = pause_job(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to pause job")

    logger.info(
        f"Job paused: {job_id}",
        event_type="scheduler_job_paused",
        job_id=job_id,
        admin_id=admin.user_id,
    )

    return {
        "message": f"Job {job_id} paused",
        "job_id": job_id,
    }


@router.post(
    "/jobs/{job_id}/resume",
    summary="Resume job",
    description="Resume a paused job.",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def resume_scheduled_job(
    job_id: str,
    admin: AdminUser = Depends(require_admin_role(AdminRole.OPERATOR)),
):
    """
    Resume a paused job.

    Args:
        job_id: Job ID to resume

    Returns:
        Confirmation message.
    """
    job = get_job_info(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    success = resume_job(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to resume job")

    logger.info(
        f"Job resumed: {job_id}",
        event_type="scheduler_job_resumed",
        job_id=job_id,
        admin_id=admin.user_id,
    )

    return {
        "message": f"Job {job_id} resumed",
        "job_id": job_id,
    }


@router.get(
    "/history",
    summary="Get all job history",
    description="Get execution history for all jobs.",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def get_all_history(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
    status: Annotated[
        str | None,
        Query(description="Filter by status"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum results"),
    ] = 50,
):
    """
    Get execution history for all jobs.

    Args:
        status: Filter by execution status
        limit: Maximum number of records

    Returns:
        List of execution records across all jobs.
    """
    history = await get_job_history(status=status, limit=limit)

    return {
        "history": history,
        "count": len(history),
    }


@router.get(
    "/status",
    summary="Get scheduler status",
    description="Get the current status of the scheduler.",
    dependencies=[Depends(check_scheduler_enabled)],
)
async def get_scheduler_status(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
):
    """
    Get scheduler status.

    Returns:
        Scheduler status including running state and job count.
    """
    scheduler = get_scheduler()

    if scheduler is None:
        return {
            "running": False,
            "job_count": 0,
            "enabled": settings.scheduler_enabled,
        }

    jobs = get_all_jobs()

    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "enabled": settings.scheduler_enabled,
        "timezone": settings.scheduler_timezone,
    }
