"""
Migration: Create idempotency keys collection with TTL index.
Created: 2025-02-28

This migration creates the idempotency_keys collection for
preventing duplicate submissions, with automatic expiration.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

# Metadata
version = 2
description = "Create idempotency keys collection with TTL index"


async def up(db: AsyncIOMotorDatabase) -> None:
    """Apply migration - create idempotency collection and indexes."""

    # Create collection (if not exists)
    collections = await db.list_collection_names()
    if "idempotency_keys" not in collections:
        await db.create_collection("idempotency_keys")

    idempotency = db["idempotency_keys"]

    # Unique index on the key
    await idempotency.create_index(
        [("key", 1)],
        name="idx_key_unique",
        unique=True,
        background=True,
    )

    # TTL index for automatic expiration (24 hours)
    await idempotency.create_index(
        [("created_at", 1)],
        name="idx_ttl_expiry",
        expireAfterSeconds=86400,  # 24 hours
        background=True,
    )

    # Index for user lookups
    await idempotency.create_index(
        [("user_id", 1)],
        name="idx_user_id",
        background=True,
    )


async def down(db: AsyncIOMotorDatabase) -> None:
    """Rollback migration - drop idempotency collection."""

    # Drop the entire collection
    await db.drop_collection("idempotency_keys")
