"""
v2 Application endpoints with breaking changes.

v2 API Changes:
- application_id renamed to id
- status is now an object with value and metadata
- company data is nested under company object
- HATEOAS-style _links included
- Standardized error responses
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.exceptions import DatabaseOperationError
from app.core.mongo import (
    failed_applications_collection,
    success_applications_collection,
)
from app.log.logging import logger
from app.models.application import ApplicationStatus
from app.schemas.app_jobs import FilterParams, JobApplicationRequest, PaginationParams
from app.services.application_uploader_service import ApplicationUploaderService
from app.services.pdf_resume_service import PdfResumeService

router = APIRouter(tags=["applications-v2"])

application_uploader = ApplicationUploaderService()
pdf_resume_service = PdfResumeService()


# =============================================================================
# v2 Response Models
# =============================================================================


class StatusObject(BaseModel):
    """v2 status object with metadata."""

    value: str
    updated_at: datetime | None = None
    message: str | None = None


class Links(BaseModel):
    """HATEOAS-style links."""

    self: str
    status: str | None = None
    jobs: str | None = None


class CompanyObject(BaseModel):
    """v2 company information."""

    name: str
    id: str | None = None


class ApplicationSubmitResponseV2(BaseModel):
    """v2 application submission response."""

    id: str = Field(..., description="Application ID")
    status: StatusObject
    job_count: int
    created_at: datetime
    links: Links = Field(..., serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ApplicationStatusResponseV2(BaseModel):
    """v2 application status response."""

    id: str
    status: StatusObject
    job_count: int | None = None
    created_at: datetime | None = None
    processed_at: datetime | None = None
    error_reason: str | None = None
    links: Links = Field(..., serialization_alias="_links")

    model_config = {"populate_by_name": True}


class JobDataV2(BaseModel):
    """v2 job data with nested company object."""

    id: str | None = None
    title: str
    description: str | None = None
    portal: str | None = None
    company: CompanyObject | None = None
    location: str | None = None
    url: str | None = None
    created_at: datetime | None = None
    links: Links | None = Field(None, serialization_alias="_links")

    model_config = {"populate_by_name": True}


class PaginationHeaders:
    """Helper class for pagination headers."""

    @staticmethod
    def set_headers(
        response: Response,
        total_count: int,
        limit: int,
        has_more: bool,
        next_cursor: str | None,
    ) -> None:
        """Set pagination headers on response."""
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Page-Size"] = str(limit)
        response.headers["X-Has-More"] = str(has_more).lower()
        if next_cursor:
            response.headers["X-Next-Cursor"] = next_cursor


# =============================================================================
# v2 Endpoints
# =============================================================================


@router.post(
    "/applications",
    summary="Submit Jobs and Save Application (v2)",
    description=(
        "v2 API with improved response structure. "
        "Returns standardized response with HATEOAS links."
    ),
    response_model=ApplicationSubmitResponseV2,
)
async def submit_jobs_and_save_application_v2(
    jobs: str = Form(...),
    cv: UploadFile | None = File(None),
    style: str | None = Form(None),
    current_user=Depends(get_current_user),
):
    """
    Submit job applications (v2).

    Changes from v1:
    - Response uses 'id' instead of 'application_id'
    - Status is an object with metadata
    - Includes _links for HATEOAS navigation
    """
    user_id = current_user

    try:
        job_request = JobApplicationRequest.model_validate_json(jobs)
    except json.JSONDecodeError as json_err:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(json_err)}")
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=f"Invalid jobs data: {str(val_err)}")

    jobs_to_apply_dicts = [job.model_dump() for job in job_request.jobs]

    cv_id = None
    if cv is not None:
        if cv.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Uploaded file must be a PDF.")
        pdf_bytes = await cv.read()
        try:
            cv_id = await pdf_resume_service.store_pdf_resume(pdf_bytes)
        except DatabaseOperationError as db_err:
            raise HTTPException(
                status_code=500, detail=f"Failed to store PDF resume: {str(db_err)}"
            )

    try:
        application_id = await application_uploader.insert_application_jobs(
            user_id=user_id, job_list_to_apply=jobs_to_apply_dicts, cv_id=cv_id, style=style
        )

        if not application_id:
            raise HTTPException(status_code=500, detail="Failed to create application")

        now = datetime.utcnow()

        return ApplicationSubmitResponseV2(
            id=application_id,
            status=StatusObject(
                value=ApplicationStatus.PENDING.value,
                updated_at=now,
                message="Application submitted successfully",
            ),
            job_count=len(jobs_to_apply_dicts),
            created_at=now,
            links=Links(
                self=f"/v2/applications/{application_id}",
                status=f"/v2/applications/{application_id}/status",
                jobs=f"/v2/applications/{application_id}/jobs",
            ),
        )

    except DatabaseOperationError as db_err:
        raise HTTPException(status_code=500, detail=f"Failed to save application: {str(db_err)}")


@router.get(
    "/applications/{application_id}/status",
    summary="Get application status (v2)",
    description="Get application status with improved response structure.",
    response_model=ApplicationStatusResponseV2,
)
async def get_application_status_v2(
    application_id: str, current_user=Depends(get_current_user)
):
    """
    Get the status of a specific application (v2).

    Changes from v1:
    - Uses 'id' instead of 'application_id'
    - Status is an object with value, updated_at, and message
    - Includes _links for navigation
    """
    try:
        status_data = await application_uploader.get_application_status(
            application_id=application_id, user_id=current_user
        )

        if not status_data:
            raise HTTPException(status_code=404, detail="Application not found")

        return ApplicationStatusResponseV2(
            id=application_id,
            status=StatusObject(
                value=status_data.get("status", "unknown"),
                updated_at=status_data.get("updated_at"),
                message=status_data.get("error_reason"),
            ),
            job_count=status_data.get("job_count"),
            created_at=status_data.get("created_at"),
            processed_at=status_data.get("processed_at"),
            error_reason=status_data.get("error_reason"),
            links=Links(
                self=f"/v2/applications/{application_id}/status",
                jobs=f"/v2/applications/{application_id}/jobs",
            ),
        )

    except DatabaseOperationError as db_err:
        logger.exception(
            "Failed to fetch application status",
            application_id=application_id,
            user=current_user,
            error=str(db_err),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch application status: {str(db_err)}"
        )


@router.get(
    "/applied",
    summary="Get successful applications (v2)",
    description=(
        "Get paginated list of successful applications. "
        "Pagination info is returned in response headers."
    ),
)
async def get_successful_applications_v2(
    response: Response,
    current_user=Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    cursor: str | None = Query(default=None, description="Pagination cursor"),
    portal: str | None = Query(default=None, description="Filter by portal"),
    company_name: str | None = Query(default=None, description="Filter by company"),
    title: str | None = Query(default=None, description="Filter by title"),
    date_from: datetime | None = Query(default=None, description="Filter from date"),
    date_to: datetime | None = Query(default=None, description="Filter until date"),
) -> list[JobDataV2]:
    """
    Get paginated and filtered list of successful applications (v2).

    Changes from v1:
    - Pagination in headers instead of response body
    - Job data includes nested company object
    - Returns array instead of object with pagination wrapper
    """
    filters = FilterParams(
        portal=portal, company_name=company_name, title=title, date_from=date_from, date_to=date_to
    )

    try:
        doc = await success_applications_collection.find_one({"user_id": current_user})

        if not doc or "content" not in doc:
            PaginationHeaders.set_headers(response, 0, limit, False, None)
            return []

        content = doc["content"]

        # Apply filters
        content = _apply_filters_v2(content, filters)

        # Paginate
        all_keys = sorted(content.keys(), reverse=True)
        total_count = len(all_keys)

        start_idx = 0
        if cursor:
            cursor_data = PaginationParams.decode_cursor(cursor)
            if cursor_data and "id" in cursor_data:
                try:
                    start_idx = all_keys.index(cursor_data["id"]) + 1
                except ValueError:
                    start_idx = 0

        page_keys = all_keys[start_idx : start_idx + limit + 1]
        has_more = len(page_keys) > limit
        page_keys = page_keys[:limit]

        next_cursor = None
        if has_more and page_keys:
            next_cursor = PaginationParams.encode_cursor(page_keys[-1])

        # Set pagination headers
        PaginationHeaders.set_headers(response, total_count, limit, has_more, next_cursor)

        # Transform to v2 format
        results = []
        for app_id in page_keys:
            job_data = content.get(app_id, {})
            results.append(_transform_to_v2(app_id, job_data))

        return results

    except Exception as e:
        logger.exception(
            "Failed to fetch successful apps for user",
            user=current_user,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch applications: {str(e)}")


def _apply_filters_v2(content: dict, filters: FilterParams) -> dict:
    """Apply filters to content dictionary (v2 version)."""
    if not any(
        [filters.portal, filters.company_name, filters.title, filters.date_from, filters.date_to]
    ):
        return content

    filtered = {}
    for app_id, job_data in content.items():
        if filters.portal:
            job_portal = job_data.get("portal", "")
            if job_portal.lower() != filters.portal.lower():
                continue

        if filters.company_name:
            company = job_data.get("company_name", "") or job_data.get("company", "")
            if filters.company_name.lower() not in company.lower():
                continue

        if filters.title:
            title = job_data.get("title", "")
            if filters.title.lower() not in title.lower():
                continue

        job_date = job_data.get("created_at") or job_data.get("applied_at")
        if job_date:
            if isinstance(job_date, str):
                try:
                    job_date = datetime.fromisoformat(job_date.replace("Z", "+00:00"))
                except ValueError:
                    job_date = None

            if job_date:
                if job_date.tzinfo is not None:
                    job_date = job_date.replace(tzinfo=None)

                if filters.date_from and job_date < filters.date_from:
                    continue
                if filters.date_to and job_date > filters.date_to:
                    continue

        filtered[app_id] = job_data

    return filtered


def _transform_to_v2(app_id: str, job_data: dict) -> JobDataV2:
    """Transform v1 job data to v2 format."""
    company_name = job_data.get("company_name") or job_data.get("company")

    return JobDataV2(
        id=app_id,
        title=job_data.get("title", ""),
        description=job_data.get("description"),
        portal=job_data.get("portal"),
        company=CompanyObject(name=company_name) if company_name else None,
        location=job_data.get("location"),
        url=job_data.get("url"),
        created_at=job_data.get("created_at"),
        links=Links(
            self=f"/v2/applied/{app_id}",
        ),
    )
