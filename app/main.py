from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.database import close_database, init_database
from app.core.metrics import MetricsMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.tracing import init_tracing, instrument_fastapi
from app.core.versioning import APIVersionMiddleware
from app.log.logging import logger

# Versioned routers
from app.routers.v1 import router as v1_router
from app.routers.v2 import router as v2_router

# Non-versioned routers (health, metrics, websocket, webhooks)
from app.routers.healthcheck_router import router as healthcheck_router
from app.routers.metrics_router import router as metrics_router
from app.routers.admin_router import router as admin_router
from app.routers.webhook_router import router as webhook_router
from app.routers.websocket_router import router as websocket_router

# Legacy routers for backward compatibility (will redirect to v1)
from app.routers.app_router import router as legacy_application_router
from app.routers.batch_router import router as legacy_batch_router
from app.routers.export_router import router as legacy_export_router


async def run_migrations():
    """Run pending database migrations if enabled."""
    if not settings.migrations_enabled or not settings.migrations_auto_run:
        logger.info("Auto-migrations disabled, skipping...")
        return

    try:
        from app.core.mongo import mongo_client
        from app.migrations.runner import MigrationRunner

        db = mongo_client[settings.mongodb_database]
        runner = MigrationRunner(db, lock_timeout=settings.migrations_lock_timeout)

        await runner.initialize()
        pending = await runner.get_pending_migrations()

        if pending:
            logger.info(
                f"Running {len(pending)} pending migration(s)...",
                event_type="migrations_starting",
                count=len(pending),
            )
            records = await runner.migrate_up()
            logger.info(
                f"Applied {len(records)} migration(s) successfully",
                event_type="migrations_complete",
                count=len(records),
            )
        else:
            logger.info("No pending migrations", event_type="migrations_up_to_date")

    except Exception as e:
        logger.error(
            f"Migration failed: {e}",
            event_type="migrations_failed",
            error=str(e),
        )
        # Don't fail startup, but log the error
        # In production, you may want to fail startup on migration errors


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

    # Run migrations
    await run_migrations()

    yield

    # Shutdown
    logger.info("Shutting down Application Manager Service...")
    await close_database()
    logger.info("Shutdown complete")


# Initialize FastAPI
app = FastAPI(
    title="Application Manager Service",
    description="Manages job application workflows with async processing",
    version="1.4.0",
    lifespan=lifespan,
)

# Add middlewares in order (last added = first executed)
# 1. Correlation ID middleware (first to run, sets up tracing context)
app.add_middleware(CorrelationIdMiddleware)

# 2. Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# 3. API Version middleware (adds version headers and deprecation notices)
app.add_middleware(APIVersionMiddleware)

# 4. Metrics middleware (captures all requests with timing)
app.add_middleware(MetricsMiddleware)

# 5. Rate limiting middleware
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)


# Root endpoint for testing
@app.get("/")
async def root():
    return {
        "message": "Application Manager Service is running!",
        "api_versions": settings.api_supported_versions,
        "default_version": settings.api_default_version,
    }


# =============================================================================
# Versioned API Routers
# =============================================================================

# Include versioned routers (primary API endpoints)
app.include_router(v1_router)
app.include_router(v2_router)

# =============================================================================
# Non-versioned Routers (Infrastructure)
# =============================================================================

# Health checks, metrics, websocket, and webhooks don't need versioning
app.include_router(healthcheck_router)
app.include_router(metrics_router)
app.include_router(websocket_router)
app.include_router(webhook_router)
app.include_router(admin_router)

# =============================================================================
# Legacy Routes (Backward Compatibility)
# =============================================================================

# Legacy routes are deprecated but maintained for backward compatibility
# They function identically to v1 but without the /v1 prefix
app.include_router(legacy_application_router, deprecated=True)
app.include_router(legacy_batch_router, deprecated=True)
app.include_router(legacy_export_router, deprecated=True)

# Instrument FastAPI for tracing
instrument_fastapi(app)
