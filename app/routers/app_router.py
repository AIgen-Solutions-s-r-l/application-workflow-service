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
from app.services.resume_ops import get_resume_by_user_id, save_application_with_resume

import logging

router = APIRouter()
settings = Settings()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
    
@router.post(
    "/applications",
    summary="Submit Jobs and Save Application",
    description=(
        "Receives a list of jobs to apply to along with user authentication via JWT,"
        "and a boolean flag indicating whether the application is a batch application. "
        "retrieves the user's resume, and saves the application data in MongoDB."
    ),
    response_description="Application ID",
    responses={
        200: {
            "description": "Application successfully saved.",
            "content": {
                "application/json": {
                    "example": {
                        "application_id": "60f6c73f4e9d3e27e4f29d9f"
                    }
                }
            }
        },
        404: {
            "description": "Resume not found for the authenticated user."
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
    Receives a list of jobs to apply from the frontend, retrieves the authenticated user's resume, 
    and saves the application data in MongoDB.

    Args:
        request (JobApplicationRequest): The request payload containing `jobs`.
        current_user: The authenticated user's ID obtained via JWT.
        is_batch (bool): A flag indicating whether the application is a batch application.

    Returns:
        dict: A dictionary containing the `application_id` of the saved application.

    Raises:
        ResumeNotFoundError: If the resume is not found.
        HTTPException: For database operation failures.
    """
    user_id = current_user  # Assuming `get_current_user` directly returns the user_id
    jobs_to_apply = request.jobs
    is_batch = request.is_batch

    try:
        # Retrieve the resume
        resume = await get_resume_by_user_id(user_id)
        if not resume:
            raise ResumeNotFoundError(user_id)

        # Convert JobItem objects to dictionaries
        jobs_to_apply_dicts = [job.model_dump() for job in jobs_to_apply]
        jobs_wrapped = {"jobs": jobs_to_apply_dicts}

        # Save the application with resume and jobs_to_apply list
        application_id = await save_application_with_resume(user_id, resume, jobs_wrapped, is_batch)

        # Ensure application_id is JSON serializable
        return {"application_id": str(application_id)}

    except ResumeNotFoundError as e:
        logger.warning(str(e))
        raise HTTPException(status_code=404, detail=str(e))
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