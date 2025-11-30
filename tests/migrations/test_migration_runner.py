"""Tests for the MigrationRunner class."""

import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.migrations.models import Migration, MigrationRecord, MigrationStatus
from app.migrations.runner import MigrationError, MigrationLockError, MigrationRunner


@pytest.fixture
def mock_db():
    """Create a mock MongoDB database."""
    db = MagicMock()
    migrations_collection = MagicMock()
    lock_collection = MagicMock()

    def get_collection(name):
        if name == "_migrations":
            return migrations_collection
        else:
            return lock_collection

    db.__getitem__ = MagicMock(side_effect=get_collection)

    return db, migrations_collection, lock_collection


@pytest.fixture
def temp_migrations_dir():
    """Create a temporary directory for test migrations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestMigrationRunner:
    """Tests for MigrationRunner."""

    def test_init(self, mock_db):
        """Test MigrationRunner initialization."""
        db, _, _ = mock_db
        runner = MigrationRunner(db)

        assert runner._db == db
        assert runner._lock_timeout == MigrationRunner.DEFAULT_LOCK_TIMEOUT

    def test_init_with_custom_timeout(self, mock_db):
        """Test MigrationRunner with custom lock timeout."""
        db, _, _ = mock_db
        runner = MigrationRunner(db, lock_timeout=600)

        assert runner._lock_timeout == 600

    @pytest.mark.asyncio
    async def test_initialize(self, mock_db):
        """Test migration system initialization."""
        db, migrations_collection, lock_collection = mock_db
        migrations_collection.create_index = AsyncMock()
        lock_collection.create_index = AsyncMock()

        runner = MigrationRunner(db)
        await runner.initialize()

        # Should create index on version
        migrations_collection.create_index.assert_called()

    def test_calculate_checksum(self, mock_db, temp_migrations_dir):
        """Test checksum calculation."""
        db, _, _ = mock_db
        runner = MigrationRunner(db)

        # Create a test file
        test_file = os.path.join(temp_migrations_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("test content")

        checksum1 = runner._calculate_checksum(test_file)
        assert isinstance(checksum1, str)
        assert len(checksum1) == 64  # SHA256 hex digest

        # Same content = same checksum
        checksum2 = runner._calculate_checksum(test_file)
        assert checksum1 == checksum2

        # Different content = different checksum
        with open(test_file, "w") as f:
            f.write("different content")
        checksum3 = runner._calculate_checksum(test_file)
        assert checksum1 != checksum3

    def test_load_migration_file_valid(self, mock_db, temp_migrations_dir):
        """Test loading a valid migration file."""
        db, _, _ = mock_db
        runner = MigrationRunner(db, migrations_dir=temp_migrations_dir)

        # Create a valid migration file
        migration_content = '''
"""Test migration."""

version = 1
description = "Test migration"

async def up(db):
    pass

async def down(db):
    pass
'''
        file_path = os.path.join(temp_migrations_dir, "001_test_migration.py")
        with open(file_path, "w") as f:
            f.write(migration_content)

        migration = runner._load_migration_file(file_path)

        assert migration is not None
        assert migration.version == 1
        assert migration.name == "test_migration"
        assert migration.description == "Test migration"
        assert callable(migration.up)
        assert callable(migration.down)

    def test_load_migration_file_invalid_filename(self, mock_db, temp_migrations_dir):
        """Test loading a file with invalid filename."""
        db, _, _ = mock_db
        runner = MigrationRunner(db, migrations_dir=temp_migrations_dir)

        # Create file with invalid name
        file_path = os.path.join(temp_migrations_dir, "invalid_name.py")
        with open(file_path, "w") as f:
            f.write("# Invalid migration")

        migration = runner._load_migration_file(file_path)
        assert migration is None

    def test_load_migration_file_missing_functions(self, mock_db, temp_migrations_dir):
        """Test loading a migration file missing up/down functions."""
        db, _, _ = mock_db
        runner = MigrationRunner(db, migrations_dir=temp_migrations_dir)

        # Create migration without up/down
        migration_content = '''
"""Missing functions."""
version = 1
description = "Missing up/down"
'''
        file_path = os.path.join(temp_migrations_dir, "001_missing.py")
        with open(file_path, "w") as f:
            f.write(migration_content)

        migration = runner._load_migration_file(file_path)
        assert migration is None

    def test_discover_migrations(self, mock_db, temp_migrations_dir):
        """Test discovering migrations from directory."""
        db, _, _ = mock_db
        runner = MigrationRunner(db, migrations_dir=temp_migrations_dir)

        # Create multiple migration files
        for i in [1, 2, 3]:
            content = f'''
version = {i}
description = "Migration {i}"

async def up(db):
    pass

async def down(db):
    pass
'''
            file_path = os.path.join(temp_migrations_dir, f"00{i}_migration_{i}.py")
            with open(file_path, "w") as f:
                f.write(content)

        migrations = runner.discover_migrations()

        assert len(migrations) == 3
        assert [m.version for m in migrations] == [1, 2, 3]

    def test_discover_migrations_sorted(self, mock_db, temp_migrations_dir):
        """Test that migrations are sorted by version."""
        db, _, _ = mock_db
        runner = MigrationRunner(db, migrations_dir=temp_migrations_dir)

        # Create files in reverse order
        for i in [3, 1, 2]:
            content = f'''
version = {i}
description = "Migration {i}"

async def up(db):
    pass

async def down(db):
    pass
'''
            file_path = os.path.join(temp_migrations_dir, f"00{i}_migration.py")
            with open(file_path, "w") as f:
                f.write(content)

        migrations = runner.discover_migrations()
        assert [m.version for m in migrations] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_applied_migrations(self, mock_db):
        """Test getting applied migrations from database."""
        db, migrations_collection, _ = mock_db

        # Mock documents
        mock_docs = [
            {
                "version": 1,
                "name": "migration_1",
                "description": "First migration",
                "applied_at": datetime.utcnow(),
                "execution_time_ms": 100,
                "status": "applied",
                "checksum": "abc123",
            },
            {
                "version": 2,
                "name": "migration_2",
                "description": "Second migration",
                "applied_at": datetime.utcnow(),
                "execution_time_ms": 200,
                "status": "applied",
                "checksum": "def456",
            },
        ]

        # Create async iterator class
        class AsyncIterator:
            def __init__(self, docs):
                self.docs = docs
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.docs):
                    raise StopAsyncIteration
                doc = self.docs[self.index]
                self.index += 1
                return doc

        mock_cursor = AsyncIterator(mock_docs)
        migrations_collection.find.return_value.sort.return_value = mock_cursor

        runner = MigrationRunner(db)
        applied = await runner.get_applied_migrations()

        assert len(applied) == 2
        assert applied[0].version == 1
        assert applied[1].version == 2

    @pytest.mark.asyncio
    async def test_get_pending_migrations(self, mock_db, temp_migrations_dir):
        """Test getting pending migrations."""
        db, migrations_collection, _ = mock_db

        # Create migration files
        for i in [1, 2, 3]:
            content = f'''
version = {i}
description = "Migration {i}"

async def up(db):
    pass

async def down(db):
    pass
'''
            file_path = os.path.join(temp_migrations_dir, f"00{i}_migration.py")
            with open(file_path, "w") as f:
                f.write(content)

        # Mock applied migrations (only version 1 applied)
        mock_docs = [
            {
                "version": 1,
                "name": "migration",
                "description": "Migration 1",
                "applied_at": datetime.utcnow(),
                "execution_time_ms": 100,
                "status": "applied",
                "checksum": "abc123",
            }
        ]

        # Create async iterator class
        class AsyncIterator:
            def __init__(self, docs):
                self.docs = docs
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.docs):
                    raise StopAsyncIteration
                doc = self.docs[self.index]
                self.index += 1
                return doc

        mock_cursor = AsyncIterator(mock_docs)
        migrations_collection.find.return_value.sort.return_value = mock_cursor

        runner = MigrationRunner(db, migrations_dir=temp_migrations_dir)
        pending = await runner.get_pending_migrations()

        assert len(pending) == 2
        assert [m.version for m in pending] == [2, 3]

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, mock_db):
        """Test successfully acquiring migration lock."""
        db, _, lock_collection = mock_db
        lock_collection.insert_one = AsyncMock()

        runner = MigrationRunner(db)
        result = await runner._acquire_lock()

        assert result is True
        lock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_failure(self, mock_db):
        """Test failing to acquire lock when already held."""
        db, _, lock_collection = mock_db
        lock_collection.insert_one = AsyncMock(side_effect=Exception("Duplicate key"))
        lock_collection.find_one = AsyncMock(
            return_value={"expires_at": datetime(2099, 1, 1)}  # Not expired
        )

        runner = MigrationRunner(db)
        result = await runner._acquire_lock()

        assert result is False

    @pytest.mark.asyncio
    async def test_release_lock(self, mock_db):
        """Test releasing migration lock."""
        db, _, lock_collection = mock_db
        lock_collection.delete_one = AsyncMock()

        runner = MigrationRunner(db)
        await runner._release_lock()

        lock_collection.delete_one.assert_called_once()


class TestMigrationModels:
    """Tests for migration data models."""

    def test_migration_record_to_dict(self):
        """Test converting MigrationRecord to dictionary."""
        record = MigrationRecord(
            version=1,
            name="test",
            description="Test migration",
            applied_at=datetime(2025, 1, 1, 12, 0, 0),
            execution_time_ms=100,
            status=MigrationStatus.APPLIED,
            checksum="abc123",
        )

        result = record.to_dict()

        assert result["version"] == 1
        assert result["name"] == "test"
        assert result["status"] == "applied"
        assert result["checksum"] == "abc123"

    def test_migration_record_from_dict(self):
        """Test creating MigrationRecord from dictionary."""
        data = {
            "version": 1,
            "name": "test",
            "description": "Test migration",
            "applied_at": datetime(2025, 1, 1, 12, 0, 0),
            "execution_time_ms": 100,
            "status": "applied",
            "checksum": "abc123",
        }

        record = MigrationRecord.from_dict(data)

        assert record.version == 1
        assert record.name == "test"
        assert record.status == MigrationStatus.APPLIED

    def test_migration_status_enum(self):
        """Test MigrationStatus enum values."""
        assert MigrationStatus.PENDING.value == "pending"
        assert MigrationStatus.APPLIED.value == "applied"
        assert MigrationStatus.FAILED.value == "failed"
        assert MigrationStatus.ROLLED_BACK.value == "rolled_back"
