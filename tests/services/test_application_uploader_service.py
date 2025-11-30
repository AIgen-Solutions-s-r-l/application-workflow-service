"""Tests for ApplicationUploaderService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import DatabaseOperationError


@pytest.fixture
def mock_deps():
    """Mock all dependencies for ApplicationUploaderService."""
    with patch(
        "app.services.application_uploader_service.applications_collection"
    ) as mock_collection, patch(
        "app.services.application_uploader_service.notification_publisher"
    ) as mock_notifier, patch(
        "app.services.application_uploader_service.application_queue_service"
    ) as mock_queue, patch(
        "app.services.application_uploader_service.settings"
    ) as mock_settings:
        # Configure mock collection
        mock_collection.insert_one = AsyncMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "mocked_application_id"
        mock_collection.insert_one.return_value = mock_result

        # Configure mock notification publisher
        mock_notifier.publish_application_submitted = AsyncMock()
        mock_notifier.publish_application_updated = AsyncMock()
        mock_notifier.publish_status_changed = AsyncMock()

        # Configure mock queue service
        mock_queue.publish_application_for_processing = AsyncMock()

        # Configure settings
        mock_settings.async_processing_enabled = True

        yield {
            "collection": mock_collection,
            "notifier": mock_notifier,
            "queue": mock_queue,
            "settings": mock_settings,
        }


@pytest.mark.asyncio
async def test_insert_application_jobs_success(mock_deps):
    """Test successful insertion of application jobs."""
    # Import service after mocks are in place
    from app.services.application_uploader_service import ApplicationUploaderService

    # Arrange
    service = ApplicationUploaderService()
    user_id = "test_user"
    job_list = [{"title": "Software Engineer", "description": "Test job"}]

    # Act
    result = await service.insert_application_jobs(user_id, job_list)

    # Assert
    assert result == "mocked_application_id"
    mock_deps["collection"].insert_one.assert_called_once()

    # Verify the document structure
    called_doc = mock_deps["collection"].insert_one.call_args[0][0]
    assert called_doc["user_id"] == user_id
    assert called_doc["jobs"] == job_list
    assert called_doc["sent"] is False
    assert called_doc["retries_left"] == 5
    assert "cv_id" in called_doc
    assert called_doc["cv_id"] is None
    assert "style" in called_doc
    assert called_doc["style"] is None

    # Verify notification was published (publish_application_submitted, not updated)
    mock_deps["notifier"].publish_application_submitted.assert_awaited_once()


@pytest.mark.asyncio
async def test_insert_application_jobs_with_cv(mock_deps):
    """Test insertion of application jobs with a CV ID."""
    from app.services.application_uploader_service import ApplicationUploaderService

    # Arrange
    service = ApplicationUploaderService()
    user_id = "test_user"
    job_list = [{"title": "Software Engineer", "description": "Test job"}]
    cv_id = "test_cv_id"

    # Act
    result = await service.insert_application_jobs(user_id, job_list, cv_id=cv_id)

    # Assert
    assert result == "mocked_application_id"
    mock_deps["collection"].insert_one.assert_called_once()

    # Verify the document structure
    called_doc = mock_deps["collection"].insert_one.call_args[0][0]
    assert called_doc["user_id"] == user_id
    assert len(called_doc["jobs"]) == 1
    # gen_cv should be False when cv_id is provided
    assert called_doc["jobs"][0]["gen_cv"] is False
    assert called_doc["cv_id"] == cv_id

    # Verify notification was published
    mock_deps["notifier"].publish_application_submitted.assert_awaited_once()


@pytest.mark.asyncio
async def test_insert_application_jobs_with_style(mock_deps):
    """Test insertion of application jobs with a style parameter."""
    from app.services.application_uploader_service import ApplicationUploaderService

    # Arrange
    service = ApplicationUploaderService()
    user_id = "test_user"
    job_list = [{"title": "Software Engineer", "description": "Test job"}]
    style = "professional"

    # Act
    result = await service.insert_application_jobs(user_id, job_list, style=style)

    # Assert
    assert result == "mocked_application_id"
    mock_deps["collection"].insert_one.assert_called_once()

    # Verify the document structure
    called_doc = mock_deps["collection"].insert_one.call_args[0][0]
    assert called_doc["style"] == style

    # Verify notification was published
    mock_deps["notifier"].publish_application_submitted.assert_awaited_once()


@pytest.mark.asyncio
async def test_insert_application_jobs_database_error():
    """Test error handling when database operation fails."""
    with patch(
        "app.services.application_uploader_service.applications_collection"
    ) as mock_collection:
        # Configure the mock to raise an exception
        mock_collection.insert_one = AsyncMock(side_effect=Exception("Database error"))

        from app.services.application_uploader_service import ApplicationUploaderService

        service = ApplicationUploaderService()
        user_id = "test_user"
        job_list = [{"title": "Software Engineer", "description": "Test job"}]

        # Act & Assert
        with pytest.raises(DatabaseOperationError) as exc_info:
            await service.insert_application_jobs(user_id, job_list)

        # Verify error message
        assert "Error inserting application data" in str(exc_info.value)
        assert "Database error" in str(exc_info.value)
