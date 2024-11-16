from fastapi import APIRouter, HTTPException
from services.resume_ops import get_resume_by_user_id, save_application_with_resume
import logging

router = APIRouter()

@router.get("/applications/{user_id}", summary="Retrieve Resume and Save Application", response_description="Application ID")
async def retrieve_and_save_application(user_id: str):
    """
    Endpoint to retrieve a user's resume based on `user_id` and save the application data.
    
    This endpoint performs the following actions:
    - Fetches the resume document associated with the specified `user_id`.
    - Saves the complete application data structure, including resume and job list.
    
    **Parameters**
    - **user_id**: The unique identifier of the user whose resume is to be retrieved.
    
    **Returns**
    - **Application ID**: The unique identifier of the saved application document in MongoDB.
    
    **Raises**
    - **404 Not Found**: If no resume is found for the specified `user_id`.
    - **500 Internal Server Error**: If an error occurs during processing.
    """
    try:
        # Fetch resume by user_id
        resume = await get_resume_by_user_id(user_id)
        
        # If no resume is found, raise a 404 error
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found for the specified user_id.")
        
        # Mock job list; replace with actual job data as needed
        job_list = [{"job_id": "job1"}, {"job_id": "job2"}]
        
        # Save application with the retrieved resume and job list
        application_id = await save_application_with_resume(user_id, resume, job_list)
        
        logging.info(f"Saved application with ID: {application_id}")
        return {"application_id": str(application_id)}
    
    except HTTPException as http_ex:
        logging.warning(f"HTTP Exception: {http_ex.detail}")
        raise http_ex
    except Exception as ex:
        logging.error(f"An error occurred: {ex}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the request.")