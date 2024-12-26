from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.core.auth import get_current_user
from app.core.config import Settings
from app.schemas.app_jobs import DetailedJobData, JobApplicationRequest, JobData
from app.services.resume_ops import upsert_application_jobs
import logging
from pydantic import ValidationError
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = Settings()

mongo_client = AsyncIOMotorClient(settings.mongodb)

@router.post(
    "/applications",
    summary="Submit Jobs and Save/Upsert Application",
    description=(
        "Receives a list of jobs to apply to along with user authentication via JWT, "
        "and upserts the application data in MongoDB by adding new jobs to the user's existing application."
    ),
    response_description="Application ID",
    responses={
        200: {
            "description": "Application successfully upserted.",
            "content": {
                "application/json": {
                    "example": {
                        "application_id": "60f6c73f4e9d3e27e4f29d9f"
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error. Failed to save application."
        }
    }
)
async def submit_jobs_and_save_application(
    request: JobApplicationRequest, current_user=Depends(get_current_user)
):
    """
    Receives a list of jobs to apply from the frontend and upserts the application data in MongoDB
    by adding the new jobs to the user's existing application document or creating a new one if it doesn't exist.

    Args:
        request (JobApplicationRequest): The request payload containing `jobs`.
        current_user: The authenticated user's ID obtained via JWT.

    Returns:
        dict: A dictionary containing the `application_id` of the saved/upserted application.

    Raises:
        HTTPException: For database operation failures.
    """
    user_id = current_user  # Assuming `get_current_user` directly returns the user_id
    jobs_to_apply = request.jobs

    try:
        # Convert JobItem objects to dictionaries
        jobs_to_apply_dicts = [job.model_dump() for job in jobs_to_apply]

        # Upsert the application: add new jobs to the existing jobs array or create a new document if none exists
        application_id = await upsert_application_jobs(user_id, jobs_to_apply_dicts)

        return {"application_id": str(application_id) if application_id else "Updated applications"}

    except Exception as e:
        logger.error(
            f"Failed to save application for user_id {user_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to save application.")
    

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

# Helper to parse the doc's content into a list of JobData (excluding fields if desired)
def parse_applications(
    doc: dict, 
    exclude_fields: Optional[List[str]] = None
) -> List[JobData]:
    """
    Given a doc (with doc['content']), parse each application into `JobData`,
    excluding fields in exclude_fields (if provided).
    """
    apps_list = []
    for app_id, raw_job_data in doc["content"].items():
        try:
            if exclude_fields:
                filtered_data = {
                    k: v 
                    for k, v in raw_job_data.items() 
                    if k not in exclude_fields
                }
            else:
                filtered_data = raw_job_data

            job_data = JobData(**filtered_data)
            apps_list.append(job_data)
        except ValidationError as e:
            logger.error(f"Validation error for app_id {app_id}: {str(e)}")
    return apps_list

# Endpoints for successful applications
# ------------------------------------------------------------------------------
@router.get(
    "/applied",
    summary="Get successful applications for the authenticated user",
    description=(
        "Fetch all successful job applications (from 'success_app' collection) "
        "for the user_id in the JWT, excluding resume and cover letter."
    ),
    response_model=List[JobData]
)
async def get_successful_applications(current_user=Depends(get_current_user)):
    try:
        doc = await fetch_user_doc(db_name="resumes", collection_name="success_app", user_id=current_user)
        apps_list = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])
        if not apps_list:
            raise HTTPException(status_code=404, detail="No valid successful applications found for this user.")
        return apps_list

    except Exception as e:
        logger.error(f"Failed to fetch successful apps for user {current_user}: {str(e)}")
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

        return DetailedJobData(**raw_job_data)

    except Exception as e:
        logger.error(f"Failed to fetch detailed info for app_id {app_id} for user {current_user}: {str(e)}")
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
    response_model=List[JobData]
)
async def get_failed_applications(current_user=Depends(get_current_user)):
    try:
        doc = await fetch_user_doc(db_name="resumes", collection_name="failed_app", user_id=current_user)
        apps_list = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])
        if not apps_list:
            raise HTTPException(status_code=404, detail="No valid failed applications found for this user.")
        return apps_list

    except Exception as e:
        logger.error(f"Failed to fetch failed apps for user {current_user}: {str(e)}")
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

        return DetailedJobData(**raw_job_data)

    except Exception as e:
        logger.error(f"Failed to fetch detailed info for app_id {app_id} for user {current_user}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch detailed application info: {str(e)}")