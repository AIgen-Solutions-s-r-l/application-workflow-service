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