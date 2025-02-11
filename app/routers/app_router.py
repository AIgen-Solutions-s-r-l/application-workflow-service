import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import ValidationError

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.exceptions import DatabaseOperationError
from app.log.logging import logger
from app.models.job import JobData
from app.schemas.app_jobs import DetailedJobData, JobApplicationRequest
from app.services.application_uploader_service import ApplicationUploaderService
from app.services.pdf_resume_service import PdfResumeService

router = APIRouter()

mongo_client = AsyncIOMotorClient(settings.mongodb)
application_uploader = ApplicationUploaderService()
pdf_resume_service = PdfResumeService()


@router.post(
    "/applications",
    summary="Submit Jobs and Save/Upsert Application",
    description=(
        "Receives a list of jobs (JSON string) and an optional PDF. "
        "If a PDF is provided, store it in `pdf_resumes`. Also upserts application data."
    ),
)
async def submit_jobs_and_save_application(
    jobs: str = Form(...),
    cv: Optional[UploadFile] = File(None),
    style: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
):
    """
    - `jobs`: JSON string that will be validated as `JobApplicationRequest`.
    - `cv`: Optional PDF file. If present, it will be stored in `pdf_resumes`
      with an empty `app_ids` array.
    """
    user_id = current_user  # Assuming `get_current_user` returns the user_id

    # Parse and validate the JSON string into the `JobApplicationRequest` model
    try:
        job_request = JobApplicationRequest.model_validate_json(jobs)
    except json.JSONDecodeError as json_err:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(json_err)}"
        )
    except ValueError as val_err:
        # model_validate_json can raise ValueError if the data doesn't match the schema
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

    # Upsert the application data
    try:
        application_id = await application_uploader.insert_application_jobs(
            user_id=user_id,
            job_list_to_apply=jobs_to_apply_dicts,
            cv_id=cv_id,
            style=style
        )
        return True if application_id else False
    except DatabaseOperationError as db_err:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save application: {str(db_err)}"
        )


# Helper to fetch the doc from MongoDB for a specific user + collection
async def fetch_user_doc(
    db_name: str,
    collection_name: str,
    user_id: str
) -> dict:
    """
    Fetch the single document from the specified `collection_name` for `user_id`.
    Raise HTTP 404 if doc not found or empty.
    """
    db = mongo_client.get_database(db_name)
    collection = db.get_collection(collection_name)

    doc = await collection.find_one({"user_id": user_id})
    if not doc or "content" not in doc or not doc["content"]:
        raise HTTPException(
            status_code=404,
            detail=f"No applications found in {collection_name} for this user."
        )
    return doc


# Helper to parse the doc's content into a dictionary of JobData
def parse_applications(
    doc: dict,
    exclude_fields: Optional[List[str]] = None
) -> Dict[str, JobData]:
    """
    Given a doc (with doc['content']), parse each application into `JobData`,
    excluding fields in `exclude_fields` (if provided), and return a dictionary
    keyed by app_id.
    """
    apps_dict = {}

    for app_id, raw_job_data in doc["content"].items():
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


# Endpoints for successful applications
# ------------------------------------------------------------------------------
@router.get(
    "/applied",
    summary="Get successful applications for the authenticated user",
    description=(
        "Fetch all successful job applications (from 'success_app' collection) "
        "for the user_id in the JWT, excluding resume and cover letter."
    ),
    response_model=Dict[str, JobData]
)
async def get_successful_applications(current_user=Depends(get_current_user)):
    try:
        doc = await fetch_user_doc(db_name="resumes", collection_name="success_app", user_id=current_user)
        apps_list = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])
        if not apps_list:
            raise HTTPException(status_code=404, detail="No valid successful applications found for this user.")
        return apps_list

    except Exception as e:
        logger.exception(
            "Failed to fetch successful apps for user {user}: {error}",
            user=current_user,
            error=str(e),
            event_type="fetch_error",
            error_type=type(e).__name__,
            error_details=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch successful apps: {str(e)}")


@router.get(
    "/applied/{app_id}",
    summary="Get detailed information about a specific successful application",
    description=(
        "Fetch resume and cover letter for a specific application ID from 'success_app' collection."
    ),
    response_model=DetailedJobData
)
async def get_successful_application_details(app_id: str, current_user=Depends(get_current_user)):
    try:
        doc = await fetch_user_doc(db_name="resumes", collection_name="success_app", user_id=current_user)
        raw_job_data = doc["content"].get(app_id)

        if not raw_job_data:
            raise HTTPException(status_code=404, detail="Application ID not found in successful applications.")

        resume_optimized = json.loads(raw_job_data["resume_optimized"]) if raw_job_data.get("resume_optimized") else None
        cover_letter = json.loads(raw_job_data["cover_letter"]) if raw_job_data.get("cover_letter") else None

        return DetailedJobData(resume_optimized=resume_optimized, cover_letter=cover_letter)

    except Exception as e:
        logger.exception(
            "Failed to fetch detailed info for app_id {app_id} for user {user}: {error}",
            app_id=app_id,
            user=current_user,
            error=str(e),
            event_type="fetch_error",
            error_type=type(e).__name__,
            error_details=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch detailed application info: {str(e)}")


# Endpoints for failed applications
# ------------------------------------------------------------------------------
@router.get(
    "/fail_applied",
    summary="Get failed applications for the authenticated user",
    description=(
        "Fetch all failed job applications (from 'failed_app' collection) "
        "for the user_id in the JWT, excluding resume and cover letter."
    ),
    response_model=Dict[str, JobData]
)
async def get_failed_applications(current_user=Depends(get_current_user)):
    try:
        doc = await fetch_user_doc(db_name="resumes", collection_name="failed_app", user_id=current_user)
        apps_list = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])
        if not apps_list:
            raise HTTPException(status_code=404, detail="No valid failed applications found for this user.")
        return apps_list

    except Exception as e:
        logger.exception(
            "Failed to fetch failed apps for user {user}: {error}",
            user=current_user,
            error=str(e),
            event_type="fetch_error",
            error_type=type(e).__name__,
            error_details=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch failed apps: {str(e)}")


@router.get(
    "/fail_applied/{app_id}",
    summary="Get detailed information about a specific failed application",
    description=(
        "Fetch resume and cover letter for a specific application ID from 'failed_app' collection."
    ),
    response_model=DetailedJobData
)
async def get_failed_application_details(app_id: str, current_user=Depends(get_current_user)):
    try:
        doc = await fetch_user_doc(db_name="resumes", collection_name="failed_app", user_id=current_user)
        raw_job_data = doc["content"].get(app_id)

        if not raw_job_data:
            raise HTTPException(status_code=404, detail="Application ID not found in failed applications.")

        resume_optimized = json.loads(raw_job_data["resume_optimized"]) if raw_job_data.get("resume_optimized") else None
        cover_letter = json.loads(raw_job_data["cover_letter"]) if raw_job_data.get("cover_letter") else None

        return DetailedJobData(resume_optimized=resume_optimized, cover_letter=cover_letter)

    except Exception as e:
        logger.exception(
            "Failed to fetch detailed info for app_id {app_id} for user {user}: {error}",
            app_id=app_id,
            user=current_user,
            error=str(e),
            event_type="fetch_error",
            error_type=type(e).__name__,
            error_details=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch detailed application info: {str(e)}")