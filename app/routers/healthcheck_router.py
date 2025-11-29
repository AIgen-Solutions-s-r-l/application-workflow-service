"""
Health check endpoints for Kubernetes probes and monitoring.

Provides:
- /health: Full health check with dependency status
- /health/live: Liveness probe (is the service running?)
- /health/ready: Readiness probe (can the service handle traffic?)
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.routers.healthchecks.fastapi_healthcheck import HealthCheckFactory, healthCheckRoute
from app.routers.healthchecks.fastapi_healthcheck_mongodb import HealthCheckMongoDB
from app.routers.healthchecks.fastapi_healthcheck_rabbitmq import HealthCheckRabbitMQ

router = APIRouter(tags=["healthcheck"])


class DependencyStatus(BaseModel):
    """Status of a single dependency."""

    name: str
    status: str  # "healthy", "unhealthy", "degraded"
    latency_ms: float | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    """Full health check response."""

    status: str  # "healthy", "unhealthy", "degraded"
    version: str = "1.0.0"
    service: str = "application-manager-service"
    environment: str
    timestamp: str
    dependencies: list[DependencyStatus] = []


class LivenessResponse(BaseModel):
    """Liveness probe response."""

    status: str = "alive"
    timestamp: str


class ReadinessResponse(BaseModel):
    """Readiness probe response."""

    status: str  # "ready", "not_ready"
    timestamp: str
    checks: dict[str, str] = {}


def _get_health_check_factory() -> HealthCheckFactory:
    """Create and configure health check factory."""
    factory = HealthCheckFactory()
    factory.add(
        HealthCheckMongoDB(
            connection_uri=settings.mongodb, alias="mongodb", tags=("database", "mongodb")
        )
    )
    factory.add(
        HealthCheckRabbitMQ(
            connection_uri=settings.rabbitmq_url, alias="rabbitmq", tags=("messaging", "rabbitmq")
        )
    )
    return factory


@router.get(
    "/health",
    summary="Full health check",
    description="Returns detailed health status including all dependencies.",
    response_model=HealthResponse,
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy or degraded"},
    },
)
async def health_check():
    """
    Full health check endpoint with dependency status.

    Returns detailed information about:
    - Overall service status
    - MongoDB connection status
    - RabbitMQ connection status
    - Response latencies
    """
    factory = _get_health_check_factory()

    try:
        result = await healthCheckRoute(factory=factory)

        # Parse the result into our response format
        dependencies = []
        overall_status = "healthy"

        for entity in result.get("entities", []):
            dep_status = "healthy" if entity.get("status") == "HEALTHY" else "unhealthy"
            if dep_status == "unhealthy":
                overall_status = "unhealthy"

            dependencies.append(
                DependencyStatus(
                    name=entity.get("alias", "unknown"), status=dep_status, message=None
                )
            )

        status_code = 200 if overall_status == "healthy" else 503

        response = HealthResponse(
            status=overall_status,
            environment=settings.environment,
            timestamp=datetime.utcnow().isoformat() + "Z",
            dependencies=dependencies,
        )

        if status_code == 503:
            raise HTTPException(status_code=503, detail=response.model_dump())

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Kubernetes liveness probe - checks if the service is running.",
    response_model=LivenessResponse,
    responses={200: {"description": "Service is alive"}},
)
async def liveness_probe():
    """
    Liveness probe for Kubernetes.

    Returns 200 if the service is running.
    This endpoint should always succeed if the process is alive.
    """
    return LivenessResponse(status="alive", timestamp=datetime.utcnow().isoformat() + "Z")


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Kubernetes readiness probe - checks if the service can handle traffic.",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "Service is ready to handle traffic"},
        503: {"description": "Service is not ready"},
    },
)
async def readiness_probe():
    """
    Readiness probe for Kubernetes.

    Returns 200 if the service can handle traffic (dependencies are available).
    Returns 503 if any critical dependency is unavailable.
    """
    factory = _get_health_check_factory()
    checks = {}
    all_ready = True

    try:
        result = await healthCheckRoute(factory=factory)

        for entity in result.get("entities", []):
            name = entity.get("alias", "unknown")
            is_healthy = entity.get("status") == "HEALTHY"
            checks[name] = "ready" if is_healthy else "not_ready"
            if not is_healthy:
                all_ready = False

        response = ReadinessResponse(
            status="ready" if all_ready else "not_ready",
            timestamp=datetime.utcnow().isoformat() + "Z",
            checks=checks,
        )

        if not all_ready:
            raise HTTPException(status_code=503, detail=response.model_dump())

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "checks": checks,
            },
        )


# Legacy endpoint for backward compatibility
@router.get(
    "/healthcheck",
    summary="Legacy health check",
    description="Legacy health check endpoint (use /health instead).",
    deprecated=True,
)
async def legacy_health_check():
    """Legacy health check endpoint - redirects to /health."""
    return await health_check()
