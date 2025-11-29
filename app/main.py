from fastapi import FastAPI
from app.routers.app_router import router as application_router
from app.routers.healthcheck_router import router as healthcheck_router
from app.routers.metrics_router import router as metrics_router
from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.metrics import MetricsMiddleware
from app.core.correlation import CorrelationIdMiddleware

# Initialize FastAPI
app = FastAPI(
    title="Application Manager Service",
    description="Manages job application workflows with async processing",
    version="1.0.0"
)

# Add middlewares in order (last added = first executed)
# 1. Correlation ID middleware (first to run, sets up tracing context)
app.add_middleware(CorrelationIdMiddleware)

# 2. Metrics middleware (captures all requests with timing)
app.add_middleware(MetricsMiddleware)

# 3. Rate limiting middleware
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# Root endpoint for testing
@app.get("/")
async def root():
    return {"message": "Application Manager Service is running!"}

# Include routers
app.include_router(application_router)
app.include_router(healthcheck_router)
app.include_router(metrics_router)