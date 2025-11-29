from fastapi import FastAPI
from app.routers.app_router import router as application_router
from app.routers.healthcheck_router import router as healthcheck_router
from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware

# Initialize FastAPI
app = FastAPI(
    title="Application Manager Service",
    description="Manages job application workflows with async processing",
    version="1.0.0"
)

# Add rate limiting middleware
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# Root endpoint for testing
@app.get("/")
async def root():
    return {"message": "Application Manager Service is running!"}

# Include the application router
app.include_router(application_router)
app.include_router(healthcheck_router)