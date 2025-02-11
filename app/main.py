from fastapi import FastAPI
from app.core.config import Settings
from app.routers.app_router import router as application_router

# Load settings
settings = Settings()

# Initialize FastAPI
app = FastAPI()

# Root endpoint for testing
@app.get("/")
async def root():
    return {"message": "Application Manager Service is running!"}

# Include the application router
app.include_router(application_router)