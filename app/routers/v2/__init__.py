"""
API v2 router aggregation.

This module aggregates all v2 API endpoints under the /v2 prefix.
v2 introduces breaking changes from v1:

Breaking Changes:
- Response field names standardized (application_id -> id)
- Nested object structures for related data
- Status is now an object with metadata, not just a string
- HATEOAS-style _links in responses
- Pagination moved to response headers

See docs/api/migration-v1-to-v2.md for full migration guide.
"""

from fastapi import APIRouter

from app.routers.v2.applications import router as applications_router

router = APIRouter(prefix="/v2", tags=["v2"])

# Include all v2 routers
router.include_router(applications_router)
