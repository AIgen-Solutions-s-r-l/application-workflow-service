# app/core/mongo.py

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import Settings

# Load MongoDB settings
settings = Settings()
MONGO_DETAILS = settings.mongodb

# Create the MongoDB client
client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.your_database_name
applications_collection = database['jobs_to_apply_per_user']
resumes_collection = database['resumes']


async def get_resume_by_user_id(user_id: str):
    """Fetch the resume document for a specific user_id from the resumes collection."""
    resume = await resumes_collection.find_one({"user_id": user_id})
    return resume.get("resume") if resume else None


async def save_application_with_resume(user_id: str, resume: dict, job_list_to_apply: list):
    """Save the application data with resume in the applications collection."""
    application_data = {
        "user_id": user_id,
        "resume": resume,
        "jobs": job_list_to_apply  # Matching `jobs` field for the applier service
    }
    result = await applications_collection.insert_one(application_data)
    return result.inserted_id
