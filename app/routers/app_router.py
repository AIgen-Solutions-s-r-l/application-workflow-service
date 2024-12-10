from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.schemas.app_jobs import JobApplicationRequest
from app.services.resume_ops import get_resume_by_user_id, save_application_with_resume
from app.core.config import Settings
from app.core.exceptions import ResumeNotFoundError
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
        "Receives a list of jobs to apply to along with user authentication via JWT, "
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

    Returns:
        dict: A dictionary containing the `application_id` of the saved application.

    Raises:
        ResumeNotFoundError: If the resume is not found.
        HTTPException: For database operation failures.
    """
    user_id = current_user  # Assuming `get_current_user` directly returns the user_id
    jobs_to_apply = request.jobs

    try:
        # Retrieve the resume
        resume = await get_resume_by_user_id(user_id)
        if not resume:
            raise ResumeNotFoundError(user_id)

        # Convert JobItem objects to dictionaries
        jobs_to_apply_dicts = [job.model_dump() for job in jobs_to_apply]
        jobs_wrapped = {"jobs": jobs_to_apply_dicts}

        # Save the application with resume and jobs_to_apply list
        application_id = await save_application_with_resume(user_id, resume, jobs_wrapped)

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