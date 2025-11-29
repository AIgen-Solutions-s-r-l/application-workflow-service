"""
Tests for Sprint 1 features:
- Story #7: Application status and timestamps
- Story #8: Status endpoint
- Story #9: Enriched notification payloads
- Story #10: Cursor-based pagination
- Story #11: Configurable database name
"""
import pytest
import json
import base64
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.models.application import ApplicationStatus, Application, ApplicationStatusResponse
from app.schemas.app_jobs import PaginationParams, PaginationInfo, PaginatedJobsResponse
from app.services.notification_service import NotificationPublisher


class TestApplicationStatus:
    """Tests for Story #7: Application status field and timestamps."""

    def test_application_status_enum_values(self):
        """Verify ApplicationStatus enum has correct values."""
        assert ApplicationStatus.PENDING.value == "pending"
        assert ApplicationStatus.PROCESSING.value == "processing"
        assert ApplicationStatus.SUCCESS.value == "success"
        assert ApplicationStatus.FAILED.value == "failed"

    def test_application_model_default_status(self):
        """Verify Application model defaults to pending status."""
        app = Application(user_id="test_user")
        assert app.status == ApplicationStatus.PENDING

    def test_application_model_timestamps_created(self):
        """Verify Application model creates timestamps on instantiation."""
        before = datetime.utcnow()
        app = Application(user_id="test_user")
        after = datetime.utcnow()

        assert app.created_at is not None
        assert app.updated_at is not None
        assert before <= app.created_at <= after
        assert before <= app.updated_at <= after
        assert app.processed_at is None

    def test_application_model_with_all_fields(self):
        """Verify Application model accepts all fields."""
        now = datetime.utcnow()
        app = Application(
            user_id="test_user",
            jobs=[{"title": "Test Job"}],
            status=ApplicationStatus.SUCCESS,
            created_at=now,
            updated_at=now,
            processed_at=now,
            cv_id="cv_123",
            style="modern",
            error_reason=None
        )

        assert app.user_id == "test_user"
        assert app.status == ApplicationStatus.SUCCESS
        assert app.processed_at == now
        assert app.cv_id == "cv_123"

    def test_application_status_response_model(self):
        """Verify ApplicationStatusResponse model structure."""
        now = datetime.utcnow()
        response = ApplicationStatusResponse(
            application_id="app_123",
            status=ApplicationStatus.PENDING,
            created_at=now,
            updated_at=now,
            job_count=5
        )

        assert response.application_id == "app_123"
        assert response.status == ApplicationStatus.PENDING
        assert response.job_count == 5
        assert response.error_reason is None


class TestNotificationPayload:
    """Tests for Story #9: Enriched notification payloads."""

    def test_build_event_payload_structure(self):
        """Verify notification payload has correct structure."""
        publisher = NotificationPublisher()
        payload = publisher._build_event_payload(
            event="application.submitted",
            application_id="app_123",
            user_id="user_456",
            status="pending",
            job_count=5
        )

        assert payload["event"] == "application.submitted"
        assert payload["version"] == "1.0"
        assert payload["application_id"] == "app_123"
        assert payload["user_id"] == "user_456"
        assert payload["status"] == "pending"
        assert payload["job_count"] == 5
        assert "timestamp" in payload
        assert payload["timestamp"].endswith("Z")

    def test_build_event_payload_with_optional_fields(self):
        """Verify optional fields are included when provided."""
        publisher = NotificationPublisher()
        payload = publisher._build_event_payload(
            event="application.status_changed",
            application_id="app_123",
            user_id="user_456",
            status="failed",
            job_count=3,
            previous_status="processing",
            error_reason="Connection timeout"
        )

        assert payload["previous_status"] == "processing"
        assert payload["error_reason"] == "Connection timeout"

    def test_build_event_payload_without_optional_fields(self):
        """Verify optional fields are excluded when not provided."""
        publisher = NotificationPublisher()
        payload = publisher._build_event_payload(
            event="application.submitted",
            application_id="app_123",
            user_id="user_456",
            status="pending",
            job_count=5
        )

        assert "previous_status" not in payload
        assert "error_reason" not in payload


class TestPagination:
    """Tests for Story #10: Cursor-based pagination."""

    def test_encode_cursor(self):
        """Verify cursor encoding works correctly."""
        cursor = PaginationParams.encode_cursor("abc123")
        decoded = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(decoded)

        assert data["id"] == "abc123"

    def test_decode_cursor_valid(self):
        """Verify cursor decoding works correctly."""
        cursor = PaginationParams.encode_cursor("test_id_456")
        result = PaginationParams.decode_cursor(cursor)

        assert result is not None
        assert result["id"] == "test_id_456"

    def test_decode_cursor_invalid(self):
        """Verify invalid cursor returns None."""
        result = PaginationParams.decode_cursor("invalid_cursor")
        assert result is None

    def test_decode_cursor_empty(self):
        """Verify empty cursor returns None."""
        result = PaginationParams.decode_cursor("")
        assert result is None

    def test_pagination_params_defaults(self):
        """Verify PaginationParams has correct defaults."""
        params = PaginationParams()
        assert params.limit == 20
        assert params.cursor is None

    def test_pagination_params_custom_limit(self):
        """Verify PaginationParams accepts custom limit."""
        params = PaginationParams(limit=50)
        assert params.limit == 50

    def test_pagination_info_structure(self):
        """Verify PaginationInfo model structure."""
        info = PaginationInfo(
            limit=20,
            next_cursor="abc123",
            has_more=True,
            total_count=100
        )

        assert info.limit == 20
        assert info.next_cursor == "abc123"
        assert info.has_more is True
        assert info.total_count == 100

    def test_paginated_jobs_response_structure(self):
        """Verify PaginatedJobsResponse model structure."""
        from app.models.job import JobData

        response = PaginatedJobsResponse(
            data={"job1": JobData(title="Test Job")},
            pagination=PaginationInfo(
                limit=20,
                has_more=False,
                total_count=1
            )
        )

        assert "job1" in response.data
        assert response.pagination.total_count == 1


class TestConfigurableDatabase:
    """Tests for Story #11: Configurable database name."""

    def test_config_has_mongodb_database_setting(self):
        """Verify config includes mongodb_database setting."""
        from app.core.config import settings

        assert hasattr(settings, 'mongodb_database')
        # Default value should be "resumes" for backward compatibility
        assert settings.mongodb_database == "resumes"

    def test_get_database_function_exists(self):
        """Verify get_database function is available."""
        from app.core.mongo import get_database

        assert callable(get_database)

    def test_collections_use_configured_database(self):
        """Verify collections are created from configured database."""
        from app.core.mongo import (
            database,
            applications_collection,
            success_applications_collection,
            failed_applications_collection
        )

        # Verify collections are defined
        assert applications_collection is not None
        assert success_applications_collection is not None
        assert failed_applications_collection is not None


class TestApplicationUploaderService:
    """Tests for updated ApplicationUploaderService with status tracking."""

    @pytest.mark.asyncio
    async def test_insert_application_sets_pending_status(self):
        """Verify new applications have pending status."""
        from app.services.application_uploader_service import ApplicationUploaderService

        with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId()
            mock_collection.insert_one = AsyncMock(return_value=mock_result)

            with patch('app.services.application_uploader_service.notification_publisher') as mock_notifier:
                mock_notifier.publish_application_submitted = AsyncMock()

                service = ApplicationUploaderService()
                app_id = await service.insert_application_jobs(
                    user_id="test_user",
                    job_list_to_apply=[{"title": "Test"}]
                )

                # Verify insert was called with pending status
                call_args = mock_collection.insert_one.call_args[0][0]
                assert call_args["status"] == "pending"
                assert "created_at" in call_args
                assert "updated_at" in call_args
                assert call_args["processed_at"] is None

    @pytest.mark.asyncio
    async def test_insert_application_publishes_submitted_notification(self):
        """Verify application submission publishes enriched notification."""
        from app.services.application_uploader_service import ApplicationUploaderService

        with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId()
            mock_collection.insert_one = AsyncMock(return_value=mock_result)

            with patch('app.services.application_uploader_service.notification_publisher') as mock_notifier:
                mock_notifier.publish_application_submitted = AsyncMock()

                service = ApplicationUploaderService()
                await service.insert_application_jobs(
                    user_id="test_user",
                    job_list_to_apply=[{"title": "Test1"}, {"title": "Test2"}]
                )

                # Verify enriched notification was published
                mock_notifier.publish_application_submitted.assert_called_once()
                call_kwargs = mock_notifier.publish_application_submitted.call_args[1]
                assert call_kwargs["user_id"] == "test_user"
                assert call_kwargs["job_count"] == 2

    @pytest.mark.asyncio
    async def test_get_application_status_returns_correct_data(self):
        """Verify get_application_status returns correct structure."""
        from app.services.application_uploader_service import ApplicationUploaderService

        test_id = ObjectId()
        now = datetime.utcnow()

        with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
            mock_collection.find_one = AsyncMock(return_value={
                "_id": test_id,
                "user_id": "test_user",
                "status": "processing",
                "created_at": now,
                "updated_at": now,
                "processed_at": None,
                "jobs": [{"title": "Test1"}, {"title": "Test2"}],
                "error_reason": None
            })

            service = ApplicationUploaderService()
            result = await service.get_application_status(
                application_id=str(test_id),
                user_id="test_user"
            )

            assert result is not None
            assert result["application_id"] == str(test_id)
            assert result["status"] == "processing"
            assert result["job_count"] == 2

    @pytest.mark.asyncio
    async def test_get_application_status_returns_none_for_not_found(self):
        """Verify get_application_status returns None when not found."""
        from app.services.application_uploader_service import ApplicationUploaderService

        with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
            mock_collection.find_one = AsyncMock(return_value=None)

            service = ApplicationUploaderService()
            result = await service.get_application_status(
                application_id=str(ObjectId()),
                user_id="test_user"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_update_application_status_sets_processed_at_on_terminal_state(self):
        """Verify processed_at is set when status becomes terminal."""
        from app.services.application_uploader_service import ApplicationUploaderService

        test_id = ObjectId()

        with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
            mock_update_result = MagicMock()
            mock_update_result.modified_count = 1
            mock_collection.update_one = AsyncMock(return_value=mock_update_result)
            mock_collection.find_one = AsyncMock(return_value={
                "user_id": "test_user",
                "jobs": []
            })

            with patch('app.services.application_uploader_service.notification_publisher') as mock_notifier:
                mock_notifier.publish_status_changed = AsyncMock()

                service = ApplicationUploaderService()
                result = await service.update_application_status(
                    application_id=str(test_id),
                    status=ApplicationStatus.SUCCESS
                )

                assert result is True
                call_args = mock_collection.update_one.call_args[0][1]
                assert "processed_at" in call_args["$set"]
