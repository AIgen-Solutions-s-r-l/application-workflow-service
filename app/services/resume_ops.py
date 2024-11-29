from app.core.mongo import resumes_collection, applications_collection

async def get_resume_by_user_id(user_id: int):
    """Fetch the resume document for a specific user_id from the resumes collection."""
    resume = await resumes_collection.find_one({"user_id": int(user_id)}, {"_id": 0, "user_id": 0})
    with open("resume.json", "w") as f:
        f.write(str(resume))
    return resume if resume else None

async def save_application_with_resume(user_id: str, resume: dict, job_list_to_apply: list):
    """Save the application data with resume in the applications collection."""
    application_data = {
        "user_id": user_id,
        "resume": resume,
        "jobs": job_list_to_apply  # Matching `jobs` field for the applier service
    }
    result = await applications_collection.insert_one(application_data)
    return result.inserted_id