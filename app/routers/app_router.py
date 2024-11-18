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
    callback=None  # Custom callback will be set up in the function
)

@router.get("/applications/{user_id}", summary="Retrieve Resume and Save Application", response_description="Application ID")
async def retrieve_and_save_application(user_id: str):
    """
    Endpoint to retrieve a user's resume based on `user_id` and save the application data.

    This endpoint performs the following actions:
    - Fetches the resume document associated with the specified `user_id`.
    - Sends the resume to RabbitMQ (apply_to_job_queue).
    - Waits for a response with the list of jobs to apply for.
    - Saves the complete application data structure, including resume and job list.

    Parameters
    - user_id: The unique identifier of the user whose resume is to be retrieved.

    Returns
    - Application ID: The unique identifier of the saved application document in MongoDB.

    Raises
    - 404 Not Found: If no resume is found for the specified `user_id`.
    - 500 Internal Server Error: For any other failure.
    """
    try:
        # Retrieve the resume
        resume = await get_resume_by_user_id(user_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Send the resume to the apply_to_job_queue
        await rabbitmq_client.send_message(queue=settings.apply_to_job_queue, message=resume)

        # Define a callback for processing received jobs_to_apply list
        def on_message_callback(ch, method, properties, body):
            # Decode message
            jobs_to_apply = body.decode('utf-8')
            # Save the application with resume and jobs_to_apply list
            application_id = save_application_with_resume(user_id, resume, jobs_to_apply)
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return application_id

        # Listen for response on job_to_apply_queue
        jobs_to_apply = await rabbitmq_client.get_jobs_to_apply(on_message_callback)

        return {"application_id": jobs_to_apply}

    except Exception as e:
        logging.error(f"Failed to retrieve and save application: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve and save application")