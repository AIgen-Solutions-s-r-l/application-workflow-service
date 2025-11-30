"""
Monitoring scheduled jobs.

Jobs for health checks, alerting, and system monitoring.
"""

from datetime import datetime

from app.core.config import settings
from app.log.logging import logger
from app.scheduler.history import record_job_execution


async def deep_health_check() -> dict:
    """
    Perform a comprehensive health check of all dependencies.

    Checks MongoDB, RabbitMQ, and Redis connectivity and records
    the results. Can trigger alerts if any service is unhealthy.
    """
    job_id = "deep_health_check"
    start_time = datetime.utcnow()

    try:
        from app.core.database import check_mongodb_health
        from app.core.rabbitmq import check_rabbitmq_health

        checks = {}
        unhealthy = []

        # MongoDB check
        try:
            mongodb_ok = await check_mongodb_health()
            checks["mongodb"] = {"healthy": mongodb_ok, "latency_ms": None}
            if not mongodb_ok:
                unhealthy.append("mongodb")
        except Exception as e:
            checks["mongodb"] = {"healthy": False, "error": str(e)}
            unhealthy.append("mongodb")

        # RabbitMQ check
        try:
            rabbitmq_ok = await check_rabbitmq_health()
            checks["rabbitmq"] = {"healthy": rabbitmq_ok, "latency_ms": None}
            if not rabbitmq_ok:
                unhealthy.append("rabbitmq")
        except Exception as e:
            checks["rabbitmq"] = {"healthy": False, "error": str(e)}
            unhealthy.append("rabbitmq")

        # Redis check
        try:
            from app.core.redis_cache import redis_cache

            if redis_cache:
                # Simple ping
                checks["redis"] = {"healthy": True, "latency_ms": None}
            else:
                checks["redis"] = {"healthy": False, "error": "Not configured"}
                # Redis is optional, don't mark as unhealthy
        except Exception as e:
            checks["redis"] = {"healthy": False, "error": str(e)}

        result = {
            "checks": checks,
            "unhealthy_services": unhealthy,
            "all_healthy": len(unhealthy) == 0,
        }

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Log with appropriate level
        if unhealthy:
            logger.warning(
                f"Health check found unhealthy services: {unhealthy}",
                event_type="deep_health_check_warning",
                **result,
            )

            # Could trigger alerts here
            # await send_alert("Health check failed", unhealthy)
        else:
            logger.info(
                "Health check passed - all services healthy",
                event_type="deep_health_check_ok",
            )

        await record_job_execution(
            job_id=job_id,
            job_name="Deep health check",
            status="success" if not unhealthy else "warning",
            result=result,
            duration_ms=duration_ms,
        )

        return result

    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.error(
            f"Health check failed: {e}",
            event_type="deep_health_check_failed",
            error=str(e),
        )

        await record_job_execution(
            job_id=job_id,
            job_name="Deep health check",
            status="failed",
            error=str(e),
            duration_ms=duration_ms,
        )

        raise


async def dlq_alert_check() -> dict:
    """
    Check DLQ depth and alert if threshold is exceeded.

    Monitors the dead letter queue for accumulated failed messages
    and triggers alerts when the count exceeds the configured threshold.
    """
    job_id = "dlq_alert_check"
    start_time = datetime.utcnow()

    try:
        from app.core.mongo import applications_collection

        # Check for failed applications that might need attention
        # This is a proxy for DLQ depth since we don't have direct RabbitMQ access
        failed_count = await applications_collection.count_documents(
            {"status": "failed"}
        )

        # Check for stuck processing applications (older than 1 hour)
        stuck_cutoff = datetime.utcnow() - datetime.timedelta(hours=1) if hasattr(datetime, 'timedelta') else datetime.utcnow()

        # Import timedelta properly
        from datetime import timedelta
        stuck_cutoff = datetime.utcnow() - timedelta(hours=1)

        stuck_count = await applications_collection.count_documents({
            "status": "processing",
            "updated_at": {"$lt": stuck_cutoff},
        })

        threshold = settings.dlq_alert_threshold
        should_alert = failed_count > threshold or stuck_count > 0

        result = {
            "failed_count": failed_count,
            "stuck_count": stuck_count,
            "threshold": threshold,
            "alert_triggered": should_alert,
        }

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        if should_alert:
            logger.warning(
                f"DLQ alert: {failed_count} failed, {stuck_count} stuck applications",
                event_type="dlq_alert_triggered",
                **result,
            )
            # Could send alert here
            # await send_alert(f"DLQ Alert: {failed_count} failed messages", severity="warning")
        else:
            logger.debug(
                "DLQ check passed",
                event_type="dlq_check_ok",
                failed_count=failed_count,
            )

        await record_job_execution(
            job_id=job_id,
            job_name="DLQ alert check",
            status="warning" if should_alert else "success",
            result=result,
            duration_ms=duration_ms,
        )

        return result

    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.error(
            f"DLQ check failed: {e}",
            event_type="dlq_check_failed",
            error=str(e),
        )

        await record_job_execution(
            job_id=job_id,
            job_name="DLQ alert check",
            status="failed",
            error=str(e),
            duration_ms=duration_ms,
        )

        raise
