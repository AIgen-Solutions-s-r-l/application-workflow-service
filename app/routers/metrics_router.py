"""
Metrics router for Prometheus endpoint.
"""
from fastapi import APIRouter, Response

from app.core.metrics import get_metrics, get_metrics_content_type

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Returns Prometheus-formatted metrics for monitoring.",
    response_class=Response
)
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    """
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )
