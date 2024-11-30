from app.core.mongo import resumes_collection, applications_collection
from app.core.exceptions import ResumeNotFoundError, DatabaseOperationError

async def get_resume_by_user_id(user_id: int):
    """
    Fetch the resume document for a specific user_id from the resumes collection.

    Args:
        user_id (int): The ID of the user whose resume is being retrieved.

    Returns:
        dict: The resume document if found.

    Raises:
        ResumeNotFoundError: If no resume is found for the provided user ID.
    """
    resume = await resumes_collection.find_one({"user_id": int(user_id)}, {"_id": 0, "user_id": 0})
    if not resume:
        raise ResumeNotFoundError(user_id)
    return resume

async def save_application_with_resume(user_id: str, resume: dict, job_list_to_apply: list):
    """
    Save the application data with resume in the applications collection.

    Args:
        user_id (str): The ID of the user applying for jobs.
        resume (dict): The user's resume data.
        job_list_to_apply (list): List of jobs the user is applying for.

    Returns:
        str: The ID of the inserted application document.

    Raises:
        DatabaseOperationError: If there is an issue saving the application to the database.
    """
    application_data = {
        "user_id": user_id,
        "resume": resume,
        "jobs": job_list_to_apply  # Matching `jobs` field for the applier service
    }
    try:
        result = await applications_collection.insert_one(application_data)
        return str(result.inserted_id)
    except Exception as e:
        raise DatabaseOperationError(f"Error inserting application data: {str(e)}")