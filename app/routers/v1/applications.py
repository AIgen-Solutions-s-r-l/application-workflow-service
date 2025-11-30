"""
v1 Application submission and status endpoints.

Provides endpoints for:
- Submitting job applications (POST /v1/applications)
- Checking application status (GET /v1/applications/{id}/status)
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.auth import get_current_user
from app.core.exceptions import DatabaseOperationError
from app.log.logging import logger
from app.models.application import (
    ApplicationStatus,
    ApplicationStatusResponse,
    ApplicationSubmitResponse,
)
from app.schemas.app_jobs import JobApplicationRequest
from app.services.application_uploader_service import ApplicationUploaderService
from app.services.pdf_resume_service import PdfResumeService

router = APIRouter(tags=["applications"])

application_uploader = ApplicationUploaderService()
pdf_resume_service = PdfResumeService()


@router.post(
    "/applications",
    summary="Submit Jobs and Save Application",
    description=(
        "Receives a list of jobs (JSON string) and an optional PDF resume. "
        "Returns a tracking ID for status monitoring."
    ),
    response_model=ApplicationSubmitResponse,
)
async def submit_jobs_and_save_application(
    jobs: str = Form(...),
    cv: UploadFile | None = File(None),
    style: str | None = Form(None),
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
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(json_err)}")
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=f"Invalid jobs data: {str(val_err)}")

    # Convert job items to dictionaries
    jobs_to_apply_dicts = [job.model_dump() for job in job_request.jobs]

    # If a PDF file is provided, store it
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

    # Insert the application
    try:
        application_id = await application_uploader.insert_application_jobs(
            user_id=user_id, job_list_to_apply=jobs_to_apply_dicts, cv_id=cv_id, style=style
        )

        if not application_id:
            raise HTTPException(status_code=500, detail="Failed to create application")

        return ApplicationSubmitResponse(
            application_id=application_id,
            status=ApplicationStatus.PENDING,
            status_url=f"/v1/applications/{application_id}/status",
            job_count=len(jobs_to_apply_dicts),
            created_at=datetime.utcnow(),
        )

    except DatabaseOperationError as db_err:
        raise HTTPException(status_code=500, detail=f"Failed to save application: {str(db_err)}")


@router.get(
    "/applications/{application_id}/status",
    summary="Get application status",
    description="Get the current status of a specific application.",
    response_model=ApplicationStatusResponse,
)
async def get_application_status(application_id: str, current_user=Depends(get_current_user)):
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
            application_id=application_id, user_id=current_user
        )

        if not status_data:
            raise HTTPException(status_code=404, detail="Application not found")

        return ApplicationStatusResponse(**status_data)

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
