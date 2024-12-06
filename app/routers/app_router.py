from fastapi import APIRouter, HTTPException
from app.schemas.app_jobs import JobApplicationRequest
from app.services.resume_ops import get_resume_by_user_id, save_application_with_resume
from app.core.config import Settings
from app.core.rabbitmq_client import AsyncRabbitMQClient
from app.core.exceptions import ResumeNotFoundError, JobApplicationError, DatabaseOperationError
import logging

router = APIRouter()
settings = Settings()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.get(
    "/applications/{user_id}",
    summary="Retrieve Resume and Save Application",
    description=(
        "Retrieves the resume of a user by their ID, sends it to a queue for job application matching, "
        "waits for a list of suitable jobs, and saves the application data."
    ),
    response_description="Application ID",
    responses={
        200: {
            "description": "Application successfully retrieved and saved.",
            "content": {
                "application/json": {
                    "example": {
                        "application_id": "60f6c73f4e9d3e27e4f29d9f"
                    }
                }
            }
        },
        404: {
            "description": "Resume not found for the provided user ID."
        },
        500: {
            "description": "Internal Server Error. Failed to retrieve and save application."
        }
    }
)
async def retrieve_and_save_application(user_id: str):
    '''
    Retrieves the resume associated with the specified `user_id`, sends it to the `apply_to_job_queue`, waits for a list
    of relevant jobs from the `job_to_apply_queue`, and saves an application entry with the resume and job list.

    Args:
        user_id (str): The ID of the user for whom to retrieve the resume.

    Returns:
        dict: A dictionary containing the `application_id` of the saved application.

    Raises:
        ResumeNotFoundError: If the resume is not found.
        JobApplicationError: For issues with the job application process.
        DatabaseOperationError: For database operation failures.
    '''
    rabbitmq_client = AsyncRabbitMQClient(
        rabbitmq_url=settings.rabbitmq_url,
        queue=settings.job_to_apply_queue
    )

    try:
        # Retrieve the resume
        resume = await get_resume_by_user_id(user_id)
        if not resume:
            raise ResumeNotFoundError(user_id)

        # Send the resume to the apply_to_job_queue
        try:
            await rabbitmq_client.send_message(queue=settings.apply_to_job_queue, message=resume)
            logger.info("Resume sent to apply_to_job_queue")
        except Exception as e:
            raise JobApplicationError(f"Failed to send resume to RabbitMQ: {str(e)}")

        # Wait for response from job_to_apply_queue
        try:
            jobs_to_apply = await rabbitmq_client.get_message()
            logger.info(f"Jobs to apply received: {jobs_to_apply}")
        except Exception as e:
            raise JobApplicationError(f"Failed to receive jobs from RabbitMQ: {str(e)}")

        # Save the application with resume and jobs_to_apply list
        application_id = await save_application_with_resume(user_id, resume, jobs_to_apply)

        # Ensure application_id is JSON serializable
        return {"application_id": str(application_id)}

    except ResumeNotFoundError as e:
        logger.warning(str(e))
        raise
    except JobApplicationError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve and save application for user_id {user_id}: {str(e)}")
        raise DatabaseOperationError("Failed to retrieve and save application")
    
@router.post(
    "/applications",
    summary="Submit Jobs and Save Application",
    description=(
        "Receives a list of jobs to apply to along with a user ID, retrieves the user's resume, "
        "and saves the application data in MongoDB."
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
            "description": "Resume not found for the provided user ID."
        },
        500: {
            "description": "Internal Server Error. Failed to save application."
        }
    }
)
async def submit_jobs_and_save_application(request: JobApplicationRequest):
    """
    Receives a list of jobs to apply from the frontend, retrieves the user's resume, and saves
    the application data in MongoDB.

    Args:
        request (JobApplicationRequest): The request payload containing `user_id` and `jobs`.

    Returns:
        dict: A dictionary containing the `application_id` of the saved application.

    Raises:
        ResumeNotFoundError: If the resume is not found.
        DatabaseOperationError: For database operation failures.
    """
    user_id = request.user_id
    jobs_to_apply = request.jobs

    try:
        # Retrieve the resume
        resume = await get_resume_by_user_id(user_id)
        if not resume:
            raise ResumeNotFoundError(user_id)

        # Save the application with resume and jobs_to_apply list
        application_id = await save_application_with_resume(user_id, resume, jobs_to_apply)

        # Ensure application_id is JSON serializable
        return {"application_id": str(application_id)}

    except ResumeNotFoundError as e:
        logger.warning(str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save application for user_id {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save application.")