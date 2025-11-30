"""
API v1 router aggregation.

This module aggregates all v1 API endpoints under the /v1 prefix.
v1 represents the current stable API version.
"""

from fastapi import APIRouter

from app.routers.v1.applications import router as applications_router
from app.routers.v1.applied import router as applied_router
from app.routers.v1.batch import router as batch_router
from app.routers.v1.export import router as export_router

router = APIRouter(prefix="/v1", tags=["v1"])

# Include all v1 routers
router.include_router(applications_router)
router.include_router(applied_router)
router.include_router(batch_router)
router.include_router(export_router)
