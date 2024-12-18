from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import Settings
from app.core.database import get_db
from app.core.exceptions import ResumeNotFoundError
from app.models.job import Job, SuccApp
from app.schemas.app_jobs import JobApplicationRequest, JobResponse
from app.services.resume_ops import upsert_application_jobs

import logging

router = APIRouter()
settings = Settings()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
    
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
    summary="Get jobs associated with the authenticated user",
    description="Fetch all jobs associated with the user_id in the JWT",
    response_model=List[JobResponse],
)
async def get_user_jobs(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch all jobs associated with the authenticated user.

    Args:
        current_user: The authenticated user's ID obtained from the JWT.
        db: Database session.

    Returns:
        List[Job]: A list of jobs associated with the user.

    Raises:
        HTTPException: If no jobs are found or a database error occurs.
    """
    user_id = current_user  # Assuming `get_current_user` directly returns the user_id

    try:
        # Query to fetch job details for the user
        logger.info(f"Fetching jobs for user_id: {user_id}")

        stmt = (
            select(Job)
            .join(SuccApp, Job.job_id == SuccApp.job_id)
            .where(SuccApp.user_id == user_id)
        )
        result = await db.execute(stmt)
        jobs = result.scalars().all()

        if not jobs:
            raise HTTPException(status_code=404, detail="No jobs found for the user.")

        return jobs

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jobs: {str(e)}")