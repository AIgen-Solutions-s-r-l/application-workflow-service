"""
Migration: Add compound index for application status queries.
Created: 2025-02-28

This migration adds optimized indexes for querying applications
by status with pagination support.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

# Metadata
version = 3
description = "Add compound index for application status queries with pagination"


async def up(db: AsyncIOMotorDatabase) -> None:
    """Apply migration - create status query indexes."""

    applications = db["jobs_to_apply_per_user"]

    # Compound index for status-based pagination queries
    # Covers: find pending applications sorted by creation date
    await applications.create_index(
        [("status", 1), ("created_at", -1), ("_id", 1)],
        name="idx_status_created_id",
        background=True,
    )

    # Index for processing queries (worker use)
    await applications.create_index(
        [("status", 1), ("retries_left", 1)],
        name="idx_status_retries",
        background=True,
    )

    # Partial index for pending applications only (more efficient)
    await applications.create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_pending_user_created",
        partialFilterExpression={"status": "pending"},
        background=True,
    )


async def down(db: AsyncIOMotorDatabase) -> None:
    """Rollback migration - drop status indexes."""

    applications = db["jobs_to_apply_per_user"]

    try:
        await applications.drop_index("idx_status_created_id")
    except Exception:
        pass

    try:
        await applications.drop_index("idx_status_retries")
    except Exception:
        pass

    try:
        await applications.drop_index("idx_pending_user_created")
    except Exception:
        pass
