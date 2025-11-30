"""
Migration 004: Create webhook collections and indexes.

Creates:
- webhooks collection with indexes on user_id, status, events
- webhook_deliveries collection with indexes on webhook_id, status, next_retry_at
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.migrations.models import Migration

migration = Migration(
    version="004",
    name="webhook_collections",
    description="Create webhook and webhook_deliveries collections with indexes",
)


async def up(db: AsyncIOMotorDatabase) -> None:
    """Apply migration: create webhook collections and indexes."""

    # Create webhooks collection indexes
    webhooks = db["webhooks"]

    # Index for user lookup
    await webhooks.create_index(
        [("user_id", ASCENDING)],
        name="idx_webhooks_user_id",
    )

    # Index for finding active webhooks by user and event type
    await webhooks.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("events", ASCENDING)],
        name="idx_webhooks_user_status_events",
    )

    # Unique index on user_id + url to prevent duplicate webhooks
    await webhooks.create_index(
        [("user_id", ASCENDING), ("url", ASCENDING)],
        name="idx_webhooks_user_url_unique",
        unique=True,
    )

    # Index for listing webhooks by status
    await webhooks.create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)],
        name="idx_webhooks_status_created",
    )

    # Create webhook_deliveries collection indexes
    deliveries = db["webhook_deliveries"]

    # Index for listing deliveries by webhook
    await deliveries.create_index(
        [("webhook_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_deliveries_webhook_created",
    )

    # Index for finding pending deliveries to retry
    await deliveries.create_index(
        [("status", ASCENDING), ("next_retry_at", ASCENDING)],
        name="idx_deliveries_status_next_retry",
    )

    # Index for user lookup
    await deliveries.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_deliveries_user_created",
    )

    # TTL index to auto-expire old deliveries after 30 days
    await deliveries.create_index(
        [("created_at", ASCENDING)],
        name="idx_deliveries_ttl",
        expireAfterSeconds=30 * 24 * 60 * 60,  # 30 days
    )


async def down(db: AsyncIOMotorDatabase) -> None:
    """Rollback migration: drop webhook indexes."""

    webhooks = db["webhooks"]
    deliveries = db["webhook_deliveries"]

    # Drop webhook indexes
    try:
        await webhooks.drop_index("idx_webhooks_user_id")
    except Exception:
        pass

    try:
        await webhooks.drop_index("idx_webhooks_user_status_events")
    except Exception:
        pass

    try:
        await webhooks.drop_index("idx_webhooks_user_url_unique")
    except Exception:
        pass

    try:
        await webhooks.drop_index("idx_webhooks_status_created")
    except Exception:
        pass

    # Drop delivery indexes
    try:
        await deliveries.drop_index("idx_deliveries_webhook_created")
    except Exception:
        pass

    try:
        await deliveries.drop_index("idx_deliveries_status_next_retry")
    except Exception:
        pass

    try:
        await deliveries.drop_index("idx_deliveries_user_created")
    except Exception:
        pass

    try:
        await deliveries.drop_index("idx_deliveries_ttl")
    except Exception:
        pass
