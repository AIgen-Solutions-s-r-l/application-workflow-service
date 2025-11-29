from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routers.app_router import router as application_router
from app.routers.healthcheck_router import router as healthcheck_router
from app.routers.metrics_router import router as metrics_router
from app.routers.websocket_router import router as websocket_router
from app.routers.batch_router import router as batch_router
from app.routers.export_router import router as export_router
from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.metrics import MetricsMiddleware
from app.core.correlation import CorrelationIdMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.database import init_database, close_database
from app.core.tracing import init_tracing, instrument_fastapi
from app.log.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Application Manager Service...")

    # Initialize tracing
    init_tracing()

    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Continue startup but log the error

    yield

    # Shutdown
    logger.info("Shutting down Application Manager Service...")
    await close_database()
    logger.info("Shutdown complete")


# Initialize FastAPI
app = FastAPI(
    title="Application Manager Service",
    description="Manages job application workflows with async processing",
    version="1.0.0",
    lifespan=lifespan
)

# Add middlewares in order (last added = first executed)
# 1. Correlation ID middleware (first to run, sets up tracing context)
app.add_middleware(CorrelationIdMiddleware)

# 2. Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# 3. Metrics middleware (captures all requests with timing)
app.add_middleware(MetricsMiddleware)

# 4. Rate limiting middleware
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
app.include_router(websocket_router)
app.include_router(batch_router)
app.include_router(export_router)

# Instrument FastAPI for tracing
instrument_fastapi(app)