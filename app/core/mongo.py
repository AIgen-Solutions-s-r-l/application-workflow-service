# app/core/mongo.py
"""
MongoDB client configuration and collection references.

This module centralizes MongoDB connection setup and provides
access to all database collections used by the application.
"""
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

# Load MongoDB settings
MONGO_DETAILS = settings.mongodb

# Create the MongoDB client
client = AsyncIOMotorClient(MONGO_DETAILS)


def get_database():
    """
    Get the configured MongoDB database.

    Returns:
        The MongoDB database instance.
    """
    return client[settings.mongodb_database]


# Database reference using configurable name
database = get_database()

# Collection references
applications_collection = database["jobs_to_apply_per_user"]
resumes_collection = database["resumes"]
pdf_resumes_collection = database["pdf_resumes"]
success_applications_collection = database["success_app"]
failed_applications_collection = database["failed_app"]
