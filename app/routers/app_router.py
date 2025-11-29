"""
Application router for job application endpoints.

This module provides endpoints for:
- Submitting job applications
- Checking application status
- Retrieving successful and failed applications with pagination
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from pydantic import ValidationError

from app.core.auth import get_current_user
from app.core.exceptions import DatabaseOperationError
from app.core.mongo import (
    get_database,
    success_applications_collection,
    failed_applications_collection
)
from app.log.logging import logger
from app.models.job import JobData
from app.models.application import ApplicationStatusResponse, ApplicationSubmitResponse, ApplicationStatus
from app.schemas.app_jobs import (
    DetailedJobData,
    JobApplicationRequest,
    FilterParams,
    PaginationParams,
    PaginationInfo,
    PaginatedJobsResponse
)
from app.services.application_uploader_service import ApplicationUploaderService
from app.services.pdf_resume_service import PdfResumeService

router = APIRouter()

application_uploader = ApplicationUploaderService()
pdf_resume_service = PdfResumeService()


# -----------------------------------------------------------------------------
# Application Submission
# -----------------------------------------------------------------------------

@router.post(
    "/applications",
    summary="Submit Jobs and Save Application",
    description=(
        "Receives a list of jobs (JSON string) and an optional PDF resume. "
        "Returns a tracking ID for status monitoring."
    ),
    response_model=ApplicationSubmitResponse
)
async def submit_jobs_and_save_application(
    jobs: str = Form(...),
    cv: Optional[UploadFile] = File(None),
    style: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
):
    """
    Submit job applications.

    Args:
        jobs: JSON string that will be validated as JobApplicationRequest.
        cv: Optional PDF file to store as resume.
        style: Optional resume style preference.
        current_user: Authenticated user ID from JWT.

    Returns:
        ApplicationSubmitResponse with tracking ID and status URL.
    """
    user_id = current_user

    # Parse and validate the JSON string into the JobApplicationRequest model
    try:
        job_request = JobApplicationRequest.model_validate_json(jobs)
    except json.JSONDecodeError as json_err:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(json_err)}"
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid jobs data: {str(val_err)}"
        )

    # Convert job items to dictionaries
    jobs_to_apply_dicts = [job.model_dump() for job in job_request.jobs]

    # If a PDF file is provided, store it
    cv_id = None
    if cv is not None:
        if cv.content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail="Uploaded file must be a PDF."
            )
        pdf_bytes = await cv.read()
        try:
            cv_id = await pdf_resume_service.store_pdf_resume(pdf_bytes)
        except DatabaseOperationError as db_err:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store PDF resume: {str(db_err)}"
            )

    # Insert the application
    try:
        application_id = await application_uploader.insert_application_jobs(
            user_id=user_id,
            job_list_to_apply=jobs_to_apply_dicts,
            cv_id=cv_id,
            style=style
        )

        if not application_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to create application"
            )

        return ApplicationSubmitResponse(
            application_id=application_id,
            status=ApplicationStatus.PENDING,
            status_url=f"/applications/{application_id}/status",
            job_count=len(jobs_to_apply_dicts),
            created_at=datetime.utcnow()
        )

    except DatabaseOperationError as db_err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save application: {str(db_err)}"
        )


# -----------------------------------------------------------------------------
# Application Status
# -----------------------------------------------------------------------------

@router.get(
    "/applications/{application_id}/status",
    summary="Get application status",
    description="Get the current status of a specific application.",
    response_model=ApplicationStatusResponse
)
async def get_application_status(
    application_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get the status of a specific application.

    Args:
        application_id: The application ID to check.
        current_user: Authenticated user ID from JWT.

    Returns:
        ApplicationStatusResponse with current status and timestamps.
    """
    try:
        status_data = await application_uploader.get_application_status(
            application_id=application_id,
            user_id=current_user
        )

        if not status_data:
            raise HTTPException(
                status_code=404,
                detail="Application not found"
            )

        return ApplicationStatusResponse(**status_data)

    except DatabaseOperationError as db_err:
        logger.exception(
            "Failed to fetch application status",
            application_id=application_id,
            user=current_user,
            error=str(db_err)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch application status: {str(db_err)}"
        )


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def apply_filters(content: dict, filters: FilterParams) -> dict:
    """
    Apply filters to content dictionary.

    Args:
        content: Dictionary of app_id -> job data.
        filters: Filter parameters.

    Returns:
        Filtered content dictionary.
    """
    if not any([filters.portal, filters.company_name, filters.title, filters.date_from, filters.date_to]):
        return content

    filtered = {}
    for app_id, job_data in content.items():
        # Portal filter (exact match, case-insensitive)
        if filters.portal:
            job_portal = job_data.get("portal", "")
            if job_portal.lower() != filters.portal.lower():
                continue

        # Company name filter (partial match, case-insensitive)
        if filters.company_name:
            company = job_data.get("company_name", "") or job_data.get("company", "")
            if filters.company_name.lower() not in company.lower():
                continue

        # Title filter (partial match, case-insensitive)
        if filters.title:
            title = job_data.get("title", "")
            if filters.title.lower() not in title.lower():
                continue

        # Date filters (on created_at or applied_at field)
        job_date = job_data.get("created_at") or job_data.get("applied_at")
        if job_date:
            if isinstance(job_date, str):
                try:
                    job_date = datetime.fromisoformat(job_date.replace("Z", "+00:00"))
                except ValueError:
                    job_date = None

            if job_date:
                if filters.date_from and job_date < filters.date_from:
                    continue
                if filters.date_to and job_date > filters.date_to:
                    continue

        filtered[app_id] = job_data

    return filtered


async def fetch_user_doc_paginated(
    collection,
    user_id: str,
    limit: int = 20,
    cursor: Optional[str] = None,
    filters: Optional[FilterParams] = None
) -> tuple[dict, bool, Optional[str], int]:
    """
    Fetch a user's document with pagination and filtering support.

    Args:
        collection: MongoDB collection to query.
        user_id: The user ID to filter by.
        limit: Maximum number of items to return.
        cursor: Pagination cursor (encoded last document ID).
        filters: Optional filter parameters.

    Returns:
        Tuple of (document, has_more, next_cursor, total_count).
    """
    # Fetch the user's document
    doc = await collection.find_one({"user_id": user_id})

    if not doc or "content" not in doc or not doc["content"]:
        return None, False, None, 0

    content = doc["content"]

    # Apply filters if provided
    if filters:
        content = apply_filters(content, filters)

    if not content:
        return None, False, None, 0

    # Get all content keys sorted (for consistent pagination)
    all_keys = sorted(content.keys(), reverse=True)
    total_count = len(all_keys)

    # Apply cursor filtering on content keys
    start_idx = 0
    if cursor:
        cursor_data = PaginationParams.decode_cursor(cursor)
        if cursor_data and "id" in cursor_data:
            try:
                start_idx = all_keys.index(cursor_data["id"]) + 1
            except ValueError:
                start_idx = 0

    # Get the slice of keys for this page
    page_keys = all_keys[start_idx:start_idx + limit + 1]
    has_more = len(page_keys) > limit
    page_keys = page_keys[:limit]

    # Build paginated content
    paginated_content = {k: content[k] for k in page_keys if k in content}

    # Create modified doc with paginated content
    paginated_doc = {**doc, "content": paginated_content}

    # Get next cursor
    next_cursor = None
    if has_more and page_keys:
        next_cursor = PaginationParams.encode_cursor(page_keys[-1])

    return paginated_doc, has_more, next_cursor, total_count


def parse_applications(
    doc: dict,
    exclude_fields: Optional[List[str]] = None
) -> Dict[str, JobData]:
    """
    Parse document content into JobData dictionary.

    Args:
        doc: Document with 'content' field.
        exclude_fields: Fields to exclude from job data.

    Returns:
        Dictionary of app_id -> JobData.
    """
    apps_dict = {}

    for app_id, raw_job_data in doc.get("content", {}).items():
        try:
            filtered_data = (
                {k: v for k, v in raw_job_data.items() if k not in exclude_fields}
                if exclude_fields
                else raw_job_data
            )
            job_data = JobData(**filtered_data)
            apps_dict[app_id] = job_data
        except ValidationError as e:
            logger.error(
                "Validation error for app_id {app_id}: {error}",
                app_id=app_id,
                error=str(e),
                event_type="validation_error"
            )
    return apps_dict


# -----------------------------------------------------------------------------
# Successful Applications
# -----------------------------------------------------------------------------

@router.get(
    "/applied",
    summary="Get successful applications for the authenticated user",
    description=(
        "Fetch all successful job applications with pagination and filtering, "
        "excluding resume and cover letter."
    ),
    response_model=PaginatedJobsResponse
)
async def get_successful_applications(
    current_user=Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    cursor: Optional[str] = Query(default=None, description="Pagination cursor"),
    portal: Optional[str] = Query(default=None, description="Filter by portal (e.g., LinkedIn)"),
    company_name: Optional[str] = Query(default=None, description="Filter by company name"),
    title: Optional[str] = Query(default=None, description="Filter by job title"),
    date_from: Optional[datetime] = Query(default=None, description="Filter from date (ISO 8601)"),
    date_to: Optional[datetime] = Query(default=None, description="Filter until date (ISO 8601)")
):
    """
    Get paginated and filtered list of successful applications.

    Args:
        current_user: Authenticated user ID from JWT.
        limit: Number of items per page (1-100).
        cursor: Pagination cursor for next page.
        portal: Filter by job portal.
        company_name: Filter by company name (partial match).
        title: Filter by job title (partial match).
        date_from: Filter applications from this date.
        date_to: Filter applications until this date.

    Returns:
        PaginatedJobsResponse with applications and pagination info.
    """
    filters = FilterParams(
        portal=portal,
        company_name=company_name,
        title=title,
        date_from=date_from,
        date_to=date_to
    )

    try:
        doc, has_more, next_cursor, total_count = await fetch_user_doc_paginated(
            collection=success_applications_collection,
            user_id=current_user,
            limit=limit,
            cursor=cursor,
            filters=filters
        )

        if not doc:
            return PaginatedJobsResponse(
                data={},
                pagination=PaginationInfo(
                    limit=limit,
                    next_cursor=None,
                    has_more=False,
                    total_count=0
                )
            )

        apps_dict = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])

        return PaginatedJobsResponse(
            data=apps_dict,
            pagination=PaginationInfo(
                limit=limit,
                next_cursor=next_cursor,
                has_more=has_more,
                total_count=total_count
            )
        )

    except Exception as e:
        logger.exception(
            "Failed to fetch successful apps for user {user}: {error}",
            user=current_user,
            error=str(e),
            event_type="fetch_error"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch successful apps: {str(e)}"
        )


@router.get(
    "/applied/{app_id}",
    summary="Get detailed information about a specific successful application",
    description=(
        "Fetch resume and cover letter for a specific application ID."
    ),
    response_model=DetailedJobData
)
async def get_successful_application_details(
    app_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get detailed info for a specific successful application.

    Args:
        app_id: The application ID.
        current_user: Authenticated user ID from JWT.

    Returns:
        DetailedJobData with resume_optimized and cover_letter.
    """
    try:
        doc = await success_applications_collection.find_one({"user_id": current_user})

        if not doc or "content" not in doc:
            raise HTTPException(
                status_code=404,
                detail="No applications found for this user."
            )

        raw_job_data = doc["content"].get(app_id)

        if not raw_job_data:
            raise HTTPException(
                status_code=404,
                detail="Application ID not found in successful applications."
            )

        resume_optimized = (
            json.loads(raw_job_data["resume_optimized"])
            if raw_job_data.get("resume_optimized")
            else None
        )
        cover_letter = (
            json.loads(raw_job_data["cover_letter"])
            if raw_job_data.get("cover_letter")
            else None
        )

        return DetailedJobData(
            resume_optimized=resume_optimized,
            cover_letter=cover_letter
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to fetch detailed info for app_id {app_id}: {error}",
            app_id=app_id,
            user=current_user,
            error=str(e),
            event_type="fetch_error"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch detailed application info: {str(e)}"
        )


# -----------------------------------------------------------------------------
# Failed Applications
# -----------------------------------------------------------------------------

@router.get(
    "/fail_applied",
    summary="Get failed applications for the authenticated user",
    description=(
        "Fetch all failed job applications with pagination and filtering, "
        "excluding resume and cover letter."
    ),
    response_model=PaginatedJobsResponse
)
async def get_failed_applications(
    current_user=Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    cursor: Optional[str] = Query(default=None, description="Pagination cursor"),
    portal: Optional[str] = Query(default=None, description="Filter by portal (e.g., LinkedIn)"),
    company_name: Optional[str] = Query(default=None, description="Filter by company name"),
    title: Optional[str] = Query(default=None, description="Filter by job title"),
    date_from: Optional[datetime] = Query(default=None, description="Filter from date (ISO 8601)"),
    date_to: Optional[datetime] = Query(default=None, description="Filter until date (ISO 8601)")
):
    """
    Get paginated and filtered list of failed applications.

    Args:
        current_user: Authenticated user ID from JWT.
        limit: Number of items per page (1-100).
        cursor: Pagination cursor for next page.
        portal: Filter by job portal.
        company_name: Filter by company name (partial match).
        title: Filter by job title (partial match).
        date_from: Filter applications from this date.
        date_to: Filter applications until this date.

    Returns:
        PaginatedJobsResponse with applications and pagination info.
    """
    filters = FilterParams(
        portal=portal,
        company_name=company_name,
        title=title,
        date_from=date_from,
        date_to=date_to
    )

    try:
        doc, has_more, next_cursor, total_count = await fetch_user_doc_paginated(
            collection=failed_applications_collection,
            user_id=current_user,
            limit=limit,
            cursor=cursor,
            filters=filters
        )

        if not doc:
            return PaginatedJobsResponse(
                data={},
                pagination=PaginationInfo(
                    limit=limit,
                    next_cursor=None,
                    has_more=False,
                    total_count=0
                )
            )

        apps_dict = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])

        return PaginatedJobsResponse(
            data=apps_dict,
            pagination=PaginationInfo(
                limit=limit,
                next_cursor=next_cursor,
                has_more=has_more,
                total_count=total_count
            )
        )

    except Exception as e:
        logger.exception(
            "Failed to fetch failed apps for user {user}: {error}",
            user=current_user,
            error=str(e),
            event_type="fetch_error"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch failed apps: {str(e)}"
        )


@router.get(
    "/fail_applied/{app_id}",
    summary="Get detailed information about a specific failed application",
    description=(
        "Fetch resume and cover letter for a specific failed application ID."
    ),
    response_model=DetailedJobData
)
async def get_failed_application_details(
    app_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get detailed info for a specific failed application.

    Args:
        app_id: The application ID.
        current_user: Authenticated user ID from JWT.

    Returns:
        DetailedJobData with resume_optimized and cover_letter.
    """
    try:
        doc = await failed_applications_collection.find_one({"user_id": current_user})

        if not doc or "content" not in doc:
            raise HTTPException(
                status_code=404,
                detail="No applications found for this user."
            )

        raw_job_data = doc["content"].get(app_id)

        if not raw_job_data:
            raise HTTPException(
                status_code=404,
                detail="Application ID not found in failed applications."
            )

        resume_optimized = (
            json.loads(raw_job_data["resume_optimized"])
            if raw_job_data.get("resume_optimized")
            else None
        )
        cover_letter = (
            json.loads(raw_job_data["cover_letter"])
            if raw_job_data.get("cover_letter")
            else None
        )

        return DetailedJobData(
            resume_optimized=resume_optimized,
            cover_letter=cover_letter
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to fetch detailed info for app_id {app_id}: {error}",
            app_id=app_id,
            user=current_user,
            error=str(e),
            event_type="fetch_error"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch detailed application info: {str(e)}"
        )
