from fastapi import APIRouter, HTTPException
from app.services.resume_ops import get_resume_by_user_id, save_application_with_resume
from app.core.rabbitmq_client import RabbitMQClient
from app.core.config import Settings
import logging

router = APIRouter()
settings = Settings()

# Initialize RabbitMQ client using settings from config.py
rabbitmq_client = RabbitMQClient(
    rabbitmq_url=settings.rabbitmq_url,
    queue=settings.job_to_apply_queue,
    callback=None  # We will use the custom get_jobs_to_apply method to retrieve messages
)

@router.get("/applications/{user_id}", summary="Retrieve Resume and Save Application", response_description="Application ID")
async def retrieve_and_save_application(user_id: str):
    """
    Endpoint to retrieve a user's resume based on `user_id` and save the application data.

    This endpoint performs the following actions:
    - Fetches the resume document associated with the specified `user_id`.
    - Retrieves the job list from RabbitMQ.
    - Saves the complete application data structure, including resume and job list.

    **Parameters**
    - **user_id**: The unique identifier of the user whose resume is to be retrieved.

    **Returns**
    - **Application ID**: The unique identifier of the saved application document in MongoDB.

    **Raises**
    - **404 Not Found**: If no resume is found for the specified `user_id`.
    - **500 Internal Server Error**: For any other failure.
    """
    try:
        resume = await get_resume_by_user_id(user_id)
        if resume is None:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Retrieve jobs_to_apply list from RabbitMQ
        jobs_to_apply_list = rabbitmq_client.get_jobs_to_apply()
        
        # Save application data with retrieved job list and resume
        application_id = await save_application_with_resume(user_id, resume, jobs_to_apply_list)
        
        return {"application_id": application_id}
    except Exception as e:
        logging.error(f"Failed to retrieve and save application: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve and save application")