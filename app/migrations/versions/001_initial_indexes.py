"""
Migration: Initial indexes for performance optimization.
Created: 2025-02-28

This migration creates the initial set of indexes for:
- jobs_to_apply_per_user (applications collection)
- success_app
- failed_app
- pdf_resumes
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

# Metadata
version = 1
description = "Initial indexes for performance optimization"


async def up(db: AsyncIOMotorDatabase) -> None:
    """Apply migration - create indexes."""

    # Applications collection (jobs_to_apply_per_user)
    applications = db["jobs_to_apply_per_user"]

    # Index for user queries with status filter
    await applications.create_index(
        [("user_id", 1), ("status", 1)],
        name="idx_user_status",
        background=True,
    )

    # Index for sorting by creation date
    await applications.create_index(
        [("created_at", -1)],
        name="idx_created_at",
        background=True,
    )

    # Compound index for user + date queries
    await applications.create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_user_created",
        background=True,
    )

    # Success applications collection
    success_app = db["success_app"]

    await success_app.create_index(
        [("user_id", 1)],
        name="idx_user_id",
        background=True,
    )

    # Failed applications collection
    failed_app = db["failed_app"]

    await failed_app.create_index(
        [("user_id", 1)],
        name="idx_user_id",
        background=True,
    )

    # PDF resumes collection
    pdf_resumes = db["pdf_resumes"]

    await pdf_resumes.create_index(
        [("user_id", 1)],
        name="idx_user_id",
        background=True,
    )


async def down(db: AsyncIOMotorDatabase) -> None:
    """Rollback migration - drop indexes."""

    # Applications collection
    applications = db["jobs_to_apply_per_user"]

    try:
        await applications.drop_index("idx_user_status")
    except Exception:
        pass  # Index may not exist

    try:
        await applications.drop_index("idx_created_at")
    except Exception:
        pass

    try:
        await applications.drop_index("idx_user_created")
    except Exception:
        pass

    # Success applications
    success_app = db["success_app"]
    try:
        await success_app.drop_index("idx_user_id")
    except Exception:
        pass

    # Failed applications
    failed_app = db["failed_app"]
    try:
        await failed_app.drop_index("idx_user_id")
    except Exception:
        pass

    # PDF resumes
    pdf_resumes = db["pdf_resumes"]
    try:
        await pdf_resumes.drop_index("idx_user_id")
    except Exception:
        pass
