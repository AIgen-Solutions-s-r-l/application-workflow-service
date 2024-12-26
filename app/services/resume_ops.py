from app.core.mongo import applications_collection
from app.core.exceptions import DatabaseOperationError

async def upsert_application_jobs(user_id: str, job_list_to_apply: list):
    """
    Upsert the application data: if a document for the user does not exist, create it.
    If it exists, add the new jobs to the existing jobs array.

    Args:
        user_id (str): The ID of the user applying for jobs.
        job_list_to_apply (list): List of jobs the user is applying for.

    Returns:
        str or None: The ID of the upserted application document. If the document was updated rather than newly inserted,
        this may return None (since no new _id was created).

    Raises:
        DatabaseOperationError: If there is an issue upserting the application to the database.
    """
    try:
        # Perform the upsert operation: push new jobs into the jobs array for the given user
        result = await applications_collection.update_one(
            {"user_id": user_id},
            {"$push": {"jobs": {"$each": job_list_to_apply}}},
            upsert=True
        )

        # If a new document was created, upserted_id will hold the new _id
        return str(result.upserted_id) if result.upserted_id else None
    except Exception as e:
        raise DatabaseOperationError(f"Error upserting application data: {str(e)}")
