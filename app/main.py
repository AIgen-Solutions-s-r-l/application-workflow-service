import logging
from fastapi import FastAPI
from app.routers.app_router import router as application_router
from app.routers.healthcheck_router import router as healthcheck_router

logging.basicConfig(level=logging.WARNING)

# Initialize FastAPI
app = FastAPI()

# Root endpoint for testing
@app.get("/")
async def root():
    return {"message": "Application Manager Service is running!"}

# Include the application router
app.include_router(application_router)
app.include_router(healthcheck_router)