from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_user
from app.core.config import Settings
from app.schemas.app_jobs import JobApplicationRequest, JobData
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

@router.get(
    "/applied",
    summary="Get successful applications for the authenticated user",
    description="Fetch all successful job applications (from 'success_app' collection) for the user_id in the JWT.",
    response_model=List[JobData]
)
async def get_successful_applications(
    current_user = Depends(get_current_user),
):
    """
    Fetch all job applications that were applied successfully (moved into 'success_app').
    
    Args:
        current_user: The authenticated user's ID obtained from the JWT.

    Returns:
        List[JobData]: A list of successfully applied jobs.

    Raises:
        HTTPException(404): If no successful apps are found.
        HTTPException(500): If a server/database error occurs.
    """
    user_id = current_user  # Assuming `get_current_user` returns just the user_id

    try:
        db = mongo_client.get_database("resumes")
        success_collection = db.get_collection("success_app")

        doc = await success_collection.find_one({"user_id": user_id})
        if not doc or "content" not in doc or not doc["content"]:
            raise HTTPException(status_code=404, detail="No successful applications found for this user.")

        # Parse the content into a list of JobData objects
        apps_list = []
        for app_id, raw_job_data in doc["content"].items():
            try:
                job_data = JobData(**raw_job_data)
                apps_list.append(job_data)
            except ValidationError as e:
                logger.error(f"Validation error for app_id {app_id}: {str(e)}")

        if not apps_list:
            raise HTTPException(status_code=404, detail="No valid successful applications found for this user.")

        return apps_list

    except Exception as e:
        logger.error(f"Failed to fetch successful apps for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch successful apps: {str(e)}")


@router.get(
    "/fail_applied",
    summary="Get failed applications for the authenticated user",
    description="Fetch all failed job applications (from 'failed_app' collection) for the user_id in the JWT.",
    response_model=List[JobData],
)
async def get_failed_applications(
    current_user = Depends(get_current_user),
):
    """
    Fetch all job applications that failed to apply (moved into 'failed_app').
    
    Args:
        current_user: The authenticated user's ID obtained from the JWT.

    Returns:
        List[JobData]: A list of failed job applications.

    Raises:
        HTTPException(404): If no failed apps are found.
        HTTPException(500): If a server/database error occurs.
    """
    user_id = current_user

    try:
        db = mongo_client.get_database("resumes")
        failed_collection = db.get_collection("failed_app")

        doc = await failed_collection.find_one({"user_id": user_id})
        if not doc or "content" not in doc or not doc["content"]:
            raise HTTPException(status_code=404, detail="No failed applications found for this user.")

        # Parse the content into a list of JobData objects
        apps_list = []
        for app_id, raw_job_data in doc["content"].items():
            try:
                job_data = JobData(**raw_job_data)
                apps_list.append(job_data)
            except ValidationError as e:
                logger.error(f"Validation error for app_id {app_id}: {str(e)}")

        if not apps_list:
            raise HTTPException(status_code=404, detail="No valid failed applications found for this user.")

        return apps_list

    except Exception as e:
        logger.error(f"Failed to fetch failed apps for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch failed apps: {str(e)}")