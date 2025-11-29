"""
Prometheus metrics for application monitoring.

This module provides metrics collection for:
- HTTP request latency and counts
- Application processing metrics
- Queue and worker metrics
- Rate limiting metrics
"""

import time
from collections.abc import Callable
from functools import wraps

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

# =============================================================================
# Service Info
# =============================================================================

SERVICE_INFO = Info(
    "application_manager_service", "Information about the application manager service"
)
SERVICE_INFO.info(
    {"version": "1.0.0", "service_name": settings.service_name, "environment": settings.environment}
)


# =============================================================================
# HTTP Metrics
# =============================================================================

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

HTTP_REQUEST_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
)

HTTP_REQUEST_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "HTTP requests currently in progress", ["method", "endpoint"]
)


# =============================================================================
# Application Metrics
# =============================================================================

APPLICATIONS_SUBMITTED = Counter(
    "applications_submitted_total",
    "Total number of applications submitted",
    ["user_type"],  # authenticated, anonymous
)

APPLICATIONS_BY_STATUS = Gauge(
    "applications_by_status", "Current number of applications by status", ["status"]
)

APPLICATION_PROCESSING_DURATION = Histogram(
    "application_processing_duration_seconds",
    "Time taken to process an application",
    ["status"],  # success, failed
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

APPLICATION_JOBS_COUNT = Histogram(
    "application_jobs_count", "Number of jobs per application", buckets=(1, 2, 5, 10, 20, 50, 100)
)


# =============================================================================
# Queue Metrics
# =============================================================================

QUEUE_MESSAGES_PUBLISHED = Counter(
    "queue_messages_published_total", "Total messages published to queues", ["queue_name"]
)

QUEUE_MESSAGES_CONSUMED = Counter(
    "queue_messages_consumed_total",
    "Total messages consumed from queues",
    ["queue_name", "status"],  # success, failed, rejected
)

QUEUE_MESSAGE_PROCESSING_DURATION = Histogram(
    "queue_message_processing_duration_seconds",
    "Time taken to process a queue message",
    ["queue_name"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

DLQ_MESSAGES = Counter(
    "dlq_messages_total",
    "Total messages sent to dead letter queue",
    ["original_queue", "error_type"],
)


# =============================================================================
# Worker Metrics
# =============================================================================

WORKER_ACTIVE = Gauge("worker_active", "Whether the worker is currently active", ["worker_name"])

WORKER_RETRY_COUNT = Counter(
    "worker_retry_total", "Total number of retries by worker", ["worker_name", "attempt"]
)


# =============================================================================
# Rate Limiting Metrics
# =============================================================================

RATE_LIMIT_EXCEEDED = Counter(
    "rate_limit_exceeded_total",
    "Total number of rate limit exceeded responses",
    ["endpoint", "user_type"],
)

RATE_LIMIT_REMAINING = Gauge(
    "rate_limit_remaining", "Current remaining rate limit for monitoring", ["user_id"]
)


# =============================================================================
# Database Metrics
# =============================================================================

DB_OPERATION_DURATION = Histogram(
    "db_operation_duration_seconds",
    "Database operation duration in seconds",
    ["operation", "collection"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

DB_OPERATION_TOTAL = Counter(
    "db_operations_total", "Total database operations", ["operation", "collection", "status"]
)


# =============================================================================
# Middleware
# =============================================================================


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP request metrics.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        # Normalize endpoint path (remove IDs for better grouping)
        endpoint = self._normalize_path(request.url.path)

        HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.time() - start_time
            HTTP_REQUEST_DURATION.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).observe(duration)
            HTTP_REQUEST_TOTAL.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()
            HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path by replacing dynamic segments with placeholders.

        Examples:
            /applications/abc123/status -> /applications/{id}/status
            /applied/xyz789 -> /applied/{id}
        """
        parts = path.strip("/").split("/")
        normalized = []

        for _i, part in enumerate(parts):
            # Check if this looks like an ID (ObjectId or UUID-like)
            if len(part) == 24 or len(part) == 36 or (len(part) > 8 and "-" in part):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/" + "/".join(normalized) if normalized else "/"


# =============================================================================
# Helper Functions
# =============================================================================


def track_db_operation(operation: str, collection: str):
    """
    Decorator to track database operation metrics.

    Usage:
        @track_db_operation('find_one', 'applications')
        async def get_application(id):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                DB_OPERATION_DURATION.labels(operation=operation, collection=collection).observe(
                    duration
                )
                DB_OPERATION_TOTAL.labels(
                    operation=operation, collection=collection, status=status
                ).inc()

        return wrapper

    return decorator


def record_application_submitted(user_type: str = "authenticated"):
    """Record an application submission."""
    APPLICATIONS_SUBMITTED.labels(user_type=user_type).inc()


def record_application_processed(status: str, duration_seconds: float):
    """Record application processing completion."""
    APPLICATION_PROCESSING_DURATION.labels(status=status).observe(duration_seconds)


def record_application_jobs(count: int):
    """Record the number of jobs in an application."""
    APPLICATION_JOBS_COUNT.observe(count)


def record_queue_publish(queue_name: str):
    """Record a message published to queue."""
    QUEUE_MESSAGES_PUBLISHED.labels(queue_name=queue_name).inc()


def record_queue_consume(queue_name: str, status: str):
    """Record a message consumed from queue."""
    QUEUE_MESSAGES_CONSUMED.labels(queue_name=queue_name, status=status).inc()


def record_dlq_message(original_queue: str, error_type: str):
    """Record a message sent to DLQ."""
    DLQ_MESSAGES.labels(original_queue=original_queue, error_type=error_type).inc()


def record_rate_limit_exceeded(endpoint: str, user_type: str = "authenticated"):
    """Record a rate limit exceeded event."""
    RATE_LIMIT_EXCEEDED.labels(endpoint=endpoint, user_type=user_type).inc()


def record_worker_retry(worker_name: str, attempt: int):
    """Record a worker retry attempt."""
    WORKER_RETRY_COUNT.labels(worker_name=worker_name, attempt=str(attempt)).inc()


def set_worker_active(worker_name: str, active: bool):
    """Set worker active status."""
    WORKER_ACTIVE.labels(worker_name=worker_name).set(1 if active else 0)


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Get the content type for metrics response."""
    return CONTENT_TYPE_LATEST
