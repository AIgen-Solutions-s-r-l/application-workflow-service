"""
Database configuration with connection pooling and index management.

This module provides:
- Optimized MongoDB connection with connection pooling
- Index creation for query performance
- Database health monitoring utilities
"""
import asyncio
from typing import Optional
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.core.config import settings
from app.log.logging import logger


class DatabaseManager:
    """
    Manages MongoDB connections with connection pooling and index management.
    """

    _instance: Optional["DatabaseManager"] = None
    _client: Optional[AsyncIOMotorClient] = None
    _database: Optional[AsyncIOMotorDatabase] = None
    _indexes_created: bool = False

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> AsyncIOMotorClient:
        """Get or create the MongoDB client with connection pooling."""
        if self._client is None:
            self._client = AsyncIOMotorClient(
                settings.mongodb,
                # Connection pool settings
                maxPoolSize=settings.mongo_max_pool_size,
                minPoolSize=settings.mongo_min_pool_size,
                maxIdleTimeMS=settings.mongo_max_idle_time_ms,
                # Timeouts
                connectTimeoutMS=settings.mongo_connect_timeout_ms,
                serverSelectionTimeoutMS=settings.mongo_server_selection_timeout_ms,
                socketTimeoutMS=settings.mongo_socket_timeout_ms,
                # Performance options
                retryWrites=True,
                retryReads=True,
                # Compression
                compressors=["zstd", "snappy", "zlib"],
            )
        return self._client

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Get the configured database."""
        if self._database is None:
            self._database = self.client[settings.mongodb_database]
        return self._database

    async def create_indexes(self) -> None:
        """
        Create indexes for all collections to optimize query performance.

        This method is idempotent - indexes are only created once per application lifecycle.
        """
        if self._indexes_created:
            return

        try:
            # Applications collection indexes
            applications_indexes = [
                IndexModel([("user_id", ASCENDING)], name="idx_user_id"),
                IndexModel([("status", ASCENDING)], name="idx_status"),
                IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
                IndexModel(
                    [("user_id", ASCENDING), ("status", ASCENDING)],
                    name="idx_user_status"
                ),
                IndexModel(
                    [("user_id", ASCENDING), ("created_at", DESCENDING)],
                    name="idx_user_created"
                ),
                IndexModel(
                    [("status", ASCENDING), ("updated_at", ASCENDING)],
                    name="idx_status_updated",
                    partialFilterExpression={"status": {"$in": ["pending", "processing"]}}
                ),
            ]

            await self.database["jobs_to_apply_per_user"].create_indexes(applications_indexes)
            logger.info("Created indexes for jobs_to_apply_per_user collection")

            # Success applications collection indexes
            success_indexes = [
                IndexModel([("user_id", ASCENDING)], name="idx_user_id"),
                IndexModel(
                    [("user_id", ASCENDING), ("content.portal", ASCENDING)],
                    name="idx_user_portal"
                ),
            ]

            await self.database["success_app"].create_indexes(success_indexes)
            logger.info("Created indexes for success_app collection")

            # Failed applications collection indexes
            failed_indexes = [
                IndexModel([("user_id", ASCENDING)], name="idx_user_id"),
                IndexModel(
                    [("user_id", ASCENDING), ("content.portal", ASCENDING)],
                    name="idx_user_portal"
                ),
            ]

            await self.database["failed_app"].create_indexes(failed_indexes)
            logger.info("Created indexes for failed_app collection")

            # PDF resumes collection indexes
            pdf_indexes = [
                IndexModel([("user_id", ASCENDING)], name="idx_user_id"),
                IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
            ]

            await self.database["pdf_resumes"].create_indexes(pdf_indexes)
            logger.info("Created indexes for pdf_resumes collection")

            # Idempotency keys collection (with TTL index)
            idempotency_indexes = [
                IndexModel([("key", ASCENDING)], name="idx_key", unique=True),
                IndexModel(
                    [("created_at", ASCENDING)],
                    name="idx_ttl",
                    expireAfterSeconds=86400  # 24 hours TTL
                ),
            ]

            await self.database["idempotency_keys"].create_indexes(idempotency_indexes)
            logger.info("Created indexes for idempotency_keys collection")

            self._indexes_created = True
            logger.info("All database indexes created successfully")

        except OperationFailure as e:
            logger.error(f"Failed to create indexes: {e}")
            raise

    async def ping(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            await self.client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"Database ping failed: {e}")
            return False

    async def get_stats(self) -> dict:
        """
        Get database statistics for monitoring.

        Returns:
            Dictionary containing database stats.
        """
        try:
            stats = await self.database.command("dbStats")
            return {
                "collections": stats.get("collections", 0),
                "objects": stats.get("objects", 0),
                "data_size_mb": round(stats.get("dataSize", 0) / (1024 * 1024), 2),
                "storage_size_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 2),
                "indexes": stats.get("indexes", 0),
                "index_size_mb": round(stats.get("indexSize", 0) / (1024 * 1024), 2),
            }
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

    async def close(self) -> None:
        """Close the database connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("Database connection closed")


# Singleton instance
db_manager = DatabaseManager()


async def init_database() -> None:
    """
    Initialize database connection and create indexes.

    Call this during application startup.
    """
    logger.info("Initializing database connection...")

    # Test connection
    if await db_manager.ping():
        logger.info("Database connection established")
    else:
        raise RuntimeError("Failed to connect to database")

    # Create indexes
    await db_manager.create_indexes()


async def close_database() -> None:
    """
    Close database connection.

    Call this during application shutdown.
    """
    await db_manager.close()


# Backward compatibility exports
def get_database():
    """Get the database instance (backward compatible)."""
    return db_manager.database


# Collection references (backward compatible)
applications_collection = db_manager.database["jobs_to_apply_per_user"]
resumes_collection = db_manager.database["resumes"]
pdf_resumes_collection = db_manager.database["pdf_resumes"]
success_applications_collection = db_manager.database["success_app"]
failed_applications_collection = db_manager.database["failed_app"]
