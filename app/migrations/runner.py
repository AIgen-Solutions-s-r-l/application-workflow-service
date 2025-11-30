"""
Migration runner for executing database migrations.
"""

import hashlib
import importlib.util
import os
import re
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.log.logging import logger
from app.migrations.models import (
    Migration,
    MigrationLock,
    MigrationRecord,
    MigrationStatus,
)


class MigrationError(Exception):
    """Base exception for migration errors."""

    pass


class MigrationLockError(MigrationError):
    """Raised when unable to acquire migration lock."""

    pass


class MigrationRunner:
    """
    Manages and executes database migrations.

    Features:
    - Discovers migration files from a directory
    - Tracks applied migrations in MongoDB
    - Supports up/down migrations with rollback
    - Distributed locking to prevent concurrent migrations
    - Checksum verification to detect modified migrations
    """

    MIGRATIONS_COLLECTION = "_migrations"
    LOCK_COLLECTION = "_migration_locks"
    DEFAULT_LOCK_TIMEOUT = 300  # 5 minutes

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        migrations_dir: Optional[str] = None,
        lock_timeout: int = DEFAULT_LOCK_TIMEOUT,
    ):
        """
        Initialize the migration runner.

        Args:
            db: MongoDB database instance.
            migrations_dir: Directory containing migration files.
            lock_timeout: Lock timeout in seconds.
        """
        self._db = db
        self._migrations_dir = migrations_dir or self._default_migrations_dir()
        self._lock_timeout = lock_timeout
        self._migrations_collection = db[self.MIGRATIONS_COLLECTION]
        self._lock_collection = db[self.LOCK_COLLECTION]

    def _default_migrations_dir(self) -> str:
        """Get default migrations directory."""
        return str(Path(__file__).parent / "versions")

    async def initialize(self) -> None:
        """Initialize migration collections and indexes."""
        # Create index on version for efficient queries
        await self._migrations_collection.create_index("version", unique=True)

        # Create TTL index on lock collection for auto-expiry
        await self._lock_collection.create_index(
            "expires_at", expireAfterSeconds=0
        )

        logger.info(
            "Migration system initialized",
            event_type="migration_initialized",
            migrations_dir=self._migrations_dir,
        )

    async def _acquire_lock(self) -> bool:
        """
        Acquire distributed lock for migrations.

        Returns:
            True if lock acquired, False otherwise.
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self._lock_timeout)
        lock_id = f"{socket.gethostname()}-{os.getpid()}"

        lock = MigrationLock(
            locked_at=now,
            locked_by=lock_id,
            expires_at=expires_at,
        )

        try:
            # Try to insert lock (will fail if exists and not expired)
            await self._lock_collection.insert_one(lock.to_dict())
            logger.info(
                "Migration lock acquired",
                event_type="migration_lock_acquired",
                locked_by=lock_id,
            )
            return True
        except Exception:
            # Check if existing lock is expired
            existing = await self._lock_collection.find_one({"_id": "migration_lock"})
            if existing and existing.get("expires_at", datetime.min) < now:
                # Replace expired lock
                result = await self._lock_collection.replace_one(
                    {"_id": "migration_lock", "expires_at": {"$lt": now}},
                    lock.to_dict(),
                )
                if result.modified_count > 0:
                    logger.info(
                        "Migration lock acquired (replaced expired)",
                        event_type="migration_lock_acquired",
                        locked_by=lock_id,
                    )
                    return True
            return False

    async def _release_lock(self) -> None:
        """Release the migration lock."""
        lock_id = f"{socket.gethostname()}-{os.getpid()}"
        await self._lock_collection.delete_one(
            {"_id": "migration_lock", "locked_by": lock_id}
        )
        logger.info(
            "Migration lock released",
            event_type="migration_lock_released",
            locked_by=lock_id,
        )

    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file."""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _load_migration_file(self, file_path: str) -> Optional[Migration]:
        """
        Load a migration from a Python file.

        Args:
            file_path: Path to the migration file.

        Returns:
            Migration object if valid, None otherwise.
        """
        filename = os.path.basename(file_path)

        # Parse version from filename (e.g., 001_initial_indexes.py)
        match = re.match(r"^(\d+)_(.+)\.py$", filename)
        if not match:
            logger.warning(
                f"Skipping invalid migration filename: {filename}",
                event_type="migration_skip",
            )
            return None

        version = int(match.group(1))
        name = match.group(2)

        try:
            # Load module dynamically
            spec = importlib.util.spec_from_file_location(f"migration_{version}", file_path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Validate required functions
            if not hasattr(module, "up") or not hasattr(module, "down"):
                logger.warning(
                    f"Migration {filename} missing up/down functions",
                    event_type="migration_invalid",
                )
                return None

            description = getattr(module, "description", f"Migration {version}")
            checksum = self._calculate_checksum(file_path)

            return Migration(
                version=version,
                name=name,
                description=description,
                up=module.up,
                down=module.down,
                checksum=checksum,
                file_path=file_path,
            )

        except Exception as e:
            logger.error(
                f"Error loading migration {filename}: {e}",
                event_type="migration_load_error",
                error=str(e),
            )
            return None

    def discover_migrations(self) -> list[Migration]:
        """
        Discover all migration files in the migrations directory.

        Returns:
            List of migrations sorted by version.
        """
        migrations = []

        if not os.path.exists(self._migrations_dir):
            logger.warning(
                f"Migrations directory not found: {self._migrations_dir}",
                event_type="migrations_dir_missing",
            )
            return migrations

        for filename in sorted(os.listdir(self._migrations_dir)):
            if filename.endswith(".py") and not filename.startswith("_"):
                file_path = os.path.join(self._migrations_dir, filename)
                migration = self._load_migration_file(file_path)
                if migration:
                    migrations.append(migration)

        # Sort by version
        migrations.sort(key=lambda m: m.version)

        logger.info(
            f"Discovered {len(migrations)} migrations",
            event_type="migrations_discovered",
            count=len(migrations),
        )

        return migrations

    async def get_applied_migrations(self) -> list[MigrationRecord]:
        """
        Get list of applied migrations from database.

        Returns:
            List of migration records sorted by version.
        """
        cursor = self._migrations_collection.find(
            {"status": MigrationStatus.APPLIED.value}
        ).sort("version", 1)

        records = []
        async for doc in cursor:
            records.append(MigrationRecord.from_dict(doc))

        return records

    async def get_pending_migrations(self) -> list[Migration]:
        """
        Get list of migrations that haven't been applied.

        Returns:
            List of pending migrations.
        """
        all_migrations = self.discover_migrations()
        applied = await self.get_applied_migrations()
        applied_versions = {r.version for r in applied}

        return [m for m in all_migrations if m.version not in applied_versions]

    async def get_status(self) -> dict[str, Any]:
        """
        Get current migration status.

        Returns:
            Dictionary with migration status information.
        """
        all_migrations = self.discover_migrations()
        applied = await self.get_applied_migrations()
        pending = await self.get_pending_migrations()

        applied_versions = {r.version for r in applied}

        return {
            "total_migrations": len(all_migrations),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "current_version": max(applied_versions) if applied_versions else 0,
            "latest_version": max(m.version for m in all_migrations) if all_migrations else 0,
            "applied": [
                {
                    "version": r.version,
                    "name": r.name,
                    "applied_at": r.applied_at.isoformat(),
                    "execution_time_ms": r.execution_time_ms,
                }
                for r in applied
            ],
            "pending": [
                {"version": m.version, "name": m.name, "description": m.description}
                for m in pending
            ],
        }

    async def migrate_up(
        self, target_version: Optional[int] = None, dry_run: bool = False
    ) -> list[MigrationRecord]:
        """
        Apply pending migrations.

        Args:
            target_version: Stop at this version (apply all if None).
            dry_run: If True, don't actually apply migrations.

        Returns:
            List of applied migration records.

        Raises:
            MigrationLockError: If unable to acquire lock.
            MigrationError: If migration fails.
        """
        if not dry_run:
            if not await self._acquire_lock():
                raise MigrationLockError("Unable to acquire migration lock")

        try:
            pending = await self.get_pending_migrations()
            applied_records = []

            for migration in pending:
                if target_version and migration.version > target_version:
                    break

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Would apply migration {migration.version}: {migration.name}",
                        event_type="migration_dry_run",
                        version=migration.version,
                    )
                    continue

                logger.info(
                    f"Applying migration {migration.version}: {migration.name}",
                    event_type="migration_applying",
                    version=migration.version,
                )

                start_time = time.time()
                try:
                    await migration.up(self._db)
                    execution_time_ms = int((time.time() - start_time) * 1000)

                    record = MigrationRecord(
                        version=migration.version,
                        name=migration.name,
                        description=migration.description,
                        applied_at=datetime.utcnow(),
                        execution_time_ms=execution_time_ms,
                        status=MigrationStatus.APPLIED,
                        checksum=migration.checksum,
                    )

                    await self._migrations_collection.insert_one(record.to_dict())
                    applied_records.append(record)

                    logger.info(
                        f"Migration {migration.version} applied successfully",
                        event_type="migration_applied",
                        version=migration.version,
                        execution_time_ms=execution_time_ms,
                    )

                except Exception as e:
                    execution_time_ms = int((time.time() - start_time) * 1000)

                    record = MigrationRecord(
                        version=migration.version,
                        name=migration.name,
                        description=migration.description,
                        applied_at=datetime.utcnow(),
                        execution_time_ms=execution_time_ms,
                        status=MigrationStatus.FAILED,
                        checksum=migration.checksum,
                        error_message=str(e),
                    )

                    await self._migrations_collection.insert_one(record.to_dict())

                    logger.error(
                        f"Migration {migration.version} failed: {e}",
                        event_type="migration_failed",
                        version=migration.version,
                        error=str(e),
                    )

                    raise MigrationError(
                        f"Migration {migration.version} failed: {e}"
                    ) from e

            return applied_records

        finally:
            if not dry_run:
                await self._release_lock()

    async def migrate_down(
        self, target_version: Optional[int] = None, dry_run: bool = False
    ) -> list[MigrationRecord]:
        """
        Rollback migrations.

        Args:
            target_version: Rollback to this version (rollback one if None).
            dry_run: If True, don't actually rollback.

        Returns:
            List of rolled back migration records.

        Raises:
            MigrationLockError: If unable to acquire lock.
            MigrationError: If rollback fails.
        """
        if not dry_run:
            if not await self._acquire_lock():
                raise MigrationLockError("Unable to acquire migration lock")

        try:
            applied = await self.get_applied_migrations()
            if not applied:
                logger.info("No migrations to rollback", event_type="migration_none")
                return []

            # Sort descending to rollback in reverse order
            applied.sort(key=lambda r: r.version, reverse=True)

            all_migrations = {m.version: m for m in self.discover_migrations()}
            rolled_back = []

            for record in applied:
                if target_version is not None and record.version <= target_version:
                    break

                migration = all_migrations.get(record.version)
                if not migration:
                    logger.warning(
                        f"Migration file not found for version {record.version}",
                        event_type="migration_file_missing",
                        version=record.version,
                    )
                    continue

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Would rollback migration {migration.version}: {migration.name}",
                        event_type="migration_dry_run",
                        version=migration.version,
                    )
                    # Only rollback one if no target specified
                    if target_version is None:
                        break
                    continue

                logger.info(
                    f"Rolling back migration {migration.version}: {migration.name}",
                    event_type="migration_rolling_back",
                    version=migration.version,
                )

                start_time = time.time()
                try:
                    await migration.down(self._db)
                    execution_time_ms = int((time.time() - start_time) * 1000)

                    # Update status to rolled back
                    await self._migrations_collection.update_one(
                        {"version": migration.version},
                        {
                            "$set": {
                                "status": MigrationStatus.ROLLED_BACK.value,
                                "rolled_back_at": datetime.utcnow(),
                            }
                        },
                    )

                    record.status = MigrationStatus.ROLLED_BACK
                    rolled_back.append(record)

                    logger.info(
                        f"Migration {migration.version} rolled back successfully",
                        event_type="migration_rolled_back",
                        version=migration.version,
                        execution_time_ms=execution_time_ms,
                    )

                    # Only rollback one if no target specified
                    if target_version is None:
                        break

                except Exception as e:
                    logger.error(
                        f"Rollback of migration {migration.version} failed: {e}",
                        event_type="migration_rollback_failed",
                        version=migration.version,
                        error=str(e),
                    )
                    raise MigrationError(
                        f"Rollback of migration {migration.version} failed: {e}"
                    ) from e

            return rolled_back

        finally:
            if not dry_run:
                await self._release_lock()

    async def verify_checksums(self) -> list[dict]:
        """
        Verify that applied migrations haven't been modified.

        Returns:
            List of migrations with checksum mismatches.
        """
        applied = await self.get_applied_migrations()
        all_migrations = {m.version: m for m in self.discover_migrations()}
        mismatches = []

        for record in applied:
            migration = all_migrations.get(record.version)
            if migration and migration.checksum != record.checksum:
                mismatches.append(
                    {
                        "version": record.version,
                        "name": record.name,
                        "expected_checksum": record.checksum,
                        "actual_checksum": migration.checksum,
                    }
                )

        return mismatches
