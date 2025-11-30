"""
Migration data models and status tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


class MigrationStatus(str, Enum):
    """Status of a migration."""

    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Migration:
    """
    Represents a database migration.

    Attributes:
        version: Unique version number for ordering migrations.
        name: Human-readable name of the migration.
        description: Detailed description of what the migration does.
        up: Async function to apply the migration.
        down: Async function to rollback the migration.
        checksum: SHA256 hash of the migration file for change detection.
        file_path: Path to the migration file.
    """

    version: int
    name: str
    description: str
    up: Callable[[Any], Coroutine[Any, Any, None]]
    down: Callable[[Any], Coroutine[Any, Any, None]]
    checksum: str = ""
    file_path: str = ""


@dataclass
class MigrationRecord:
    """
    Record of a migration stored in the database.

    Attributes:
        version: Migration version number.
        name: Migration name.
        description: Migration description.
        applied_at: When the migration was applied.
        execution_time_ms: How long the migration took.
        status: Current status of the migration.
        checksum: Hash of the migration file when applied.
        error_message: Error message if migration failed.
    """

    version: int
    name: str
    description: str
    applied_at: datetime
    execution_time_ms: int
    status: MigrationStatus
    checksum: str
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "applied_at": self.applied_at,
            "execution_time_ms": self.execution_time_ms,
            "status": self.status.value,
            "checksum": self.checksum,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MigrationRecord":
        """Create from MongoDB document."""
        return cls(
            version=data["version"],
            name=data["name"],
            description=data["description"],
            applied_at=data["applied_at"],
            execution_time_ms=data["execution_time_ms"],
            status=MigrationStatus(data["status"]),
            checksum=data["checksum"],
            error_message=data.get("error_message"),
        )


@dataclass
class MigrationLock:
    """
    Distributed lock for preventing concurrent migrations.

    Attributes:
        locked_at: When the lock was acquired.
        locked_by: Identifier of the process holding the lock.
        expires_at: When the lock expires.
    """

    locked_at: datetime
    locked_by: str
    expires_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        return {
            "_id": "migration_lock",
            "locked_at": self.locked_at,
            "locked_by": self.locked_by,
            "expires_at": self.expires_at,
        }
