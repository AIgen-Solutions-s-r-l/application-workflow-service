from fastapi import APIRouter, HTTPException
from app.services.resume_ops import get_resume_by_user_id, save_application_with_resume
from app.core.config import Settings
from app.core.rabbitmq_client import AsyncRabbitMQClient
import logging

router = APIRouter()
settings = Settings()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.get("/applications/{user_id}", summary="Retrieve Resume and Save Application", response_description="Application ID")
async def retrieve_and_save_application(user_id: str):
    rabbitmq_client = AsyncRabbitMQClient(
        rabbitmq_url=settings.rabbitmq_url,
        queue=settings.job_to_apply_queue
    )

    try:
        # Retrieve the resume
        resume = await get_resume_by_user_id(user_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Send the resume to the apply_to_job_queue
        await rabbitmq_client.send_message(queue=settings.apply_to_job_queue, message=resume)
        logger.info("Resume sent to apply_to_job_queue")

        # Wait for response from job_to_apply_queue
        jobs_to_apply = await rabbitmq_client.get_message()
        logger.info(f"Jobs to apply received: {jobs_to_apply}")

        # Save the application with resume and jobs_to_apply list
        application_id = await save_application_with_resume(user_id, resume, jobs_to_apply)

        # Ensure application_id is JSON serializable
        return {"application_id": str(application_id)}

    except Exception as e:
        logger.error(f"Failed to retrieve and save application for user_id {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve and save application")
