"""
Job execution history storage.

Stores job execution records in MongoDB for debugging and monitoring.
"""

from datetime import datetime
from typing import Any

from app.core.mongo import database
from app.log.logging import logger

# Collection for job history
job_history_collection = database["job_history"]


async def record_job_execution(
    job_id: str,
    job_name: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    duration_ms: int = 0,
) -> str:
    """
    Record a job execution in the history collection.

    Args:
        job_id: Unique job identifier
        job_name: Human-readable job name
        status: Execution status (success, failed, warning, skipped)
        result: Job result data (if successful)
        error: Error message (if failed)
        duration_ms: Execution duration in milliseconds

    Returns:
        Inserted document ID
    """
    try:
        doc = {
            "job_id": job_id,
            "job_name": job_name,
            "status": status,
            "result": result,
            "error": error,
            "duration_ms": duration_ms,
            "executed_at": datetime.utcnow(),
        }

        result_insert = await job_history_collection.insert_one(doc)
        return str(result_insert.inserted_id)

    except Exception as e:
        # Don't fail job execution if history recording fails
        logger.warning(
            f"Failed to record job execution: {e}",
            event_type="job_history_error",
            job_id=job_id,
            error=str(e),
        )
        return ""


async def get_job_history(
    job_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get job execution history.

    Args:
        job_id: Filter by job ID
        status: Filter by status
        limit: Maximum number of records

    Returns:
        List of job execution records
    """
    query = {}
    if job_id:
        query["job_id"] = job_id
    if status:
        query["status"] = status

    cursor = job_history_collection.find(query).sort("executed_at", -1).limit(limit)

    records = []
    async for doc in cursor:
        records.append({
            "id": str(doc["_id"]),
            "job_id": doc["job_id"],
            "job_name": doc["job_name"],
            "status": doc["status"],
            "result": doc.get("result"),
            "error": doc.get("error"),
            "duration_ms": doc.get("duration_ms", 0),
            "executed_at": doc["executed_at"].isoformat() + "Z" if doc.get("executed_at") else None,
        })

    return records


async def cleanup_old_history(retention_days: int = 30) -> int:
    """
    Remove job history older than retention period.

    Args:
        retention_days: Number of days to retain history

    Returns:
        Number of deleted records
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    result = await job_history_collection.delete_many(
        {"executed_at": {"$lt": cutoff}}
    )

    return result.deleted_count


async def get_job_stats(job_id: str, days: int = 7) -> dict[str, Any]:
    """
    Get execution statistics for a job.

    Args:
        job_id: Job ID to get stats for
        days: Number of days to analyze

    Returns:
        Statistics including success rate, avg duration, etc.
    """
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=days)

    pipeline = [
        {"$match": {"job_id": job_id, "executed_at": {"$gte": since}}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "avg_duration": {"$avg": "$duration_ms"},
            }
        },
    ]

    stats = {"success": 0, "failed": 0, "warning": 0, "total": 0, "avg_duration_ms": 0}

    total_duration = 0
    async for doc in job_history_collection.aggregate(pipeline):
        status = doc["_id"]
        count = doc["count"]
        stats[status] = count
        stats["total"] += count
        if doc["avg_duration"]:
            total_duration += doc["avg_duration"] * count

    if stats["total"] > 0:
        stats["avg_duration_ms"] = int(total_duration / stats["total"])
        stats["success_rate"] = round(stats["success"] / stats["total"] * 100, 1)
    else:
        stats["success_rate"] = 0

    stats["period_days"] = days

    return stats
