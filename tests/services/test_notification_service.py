"""Tests for NotificationPublisher."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.base_publisher import BasePublisher
from app.services.notification_service import NotificationPublisher


@pytest.mark.asyncio
async def test_notification_publisher_inheritance():
    """Test that NotificationPublisher inherits from BasePublisher."""
    # Arrange & Act
    publisher = NotificationPublisher()

    # Assert
    assert isinstance(publisher, BasePublisher)


@pytest.mark.asyncio
async def test_get_queue_name():
    """Test queue name resolution from settings."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.middleware_queue = "test_middleware_queue"

    with patch("app.services.notification_service.settings", mock_settings):
        publisher = NotificationPublisher()

        # Act
        result = publisher.get_queue_name()

        # Assert
        assert result == "test_middleware_queue"


@pytest.mark.asyncio
async def test_publish_application_updated():
    """Test publishing a legacy application updated notification."""
    # Arrange
    publisher = NotificationPublisher()
    publisher.publish = AsyncMock()

    # Act
    await publisher.publish_application_updated()

    # Assert - note: publish is called with legacy payload and persistent=False
    publisher.publish.assert_awaited_once_with({"updated": True}, persistent=False)


@pytest.mark.asyncio
async def test_publish_application_updated_with_logger():
    """Test that warning logging occurs when publishing legacy notification."""
    # Arrange
    publisher = NotificationPublisher()
    publisher.publish = AsyncMock()

    with patch("app.services.notification_service.logger") as mock_logger:
        # Act
        await publisher.publish_application_updated()

        # Assert - Now logs a warning about deprecated method
        mock_logger.warning.assert_called_once()
        assert (
            "deprecated" in mock_logger.warning.call_args[0][0].lower()
        )
        assert mock_logger.warning.call_args[1]["event_type"] == "notification_publishing"
        publisher.publish.assert_awaited_once_with({"updated": True}, persistent=False)


@pytest.mark.asyncio
async def test_publish_application_submitted():
    """Test publishing application submitted notification."""
    # Arrange
    publisher = NotificationPublisher()
    publisher.publish = AsyncMock()

    # Act
    await publisher.publish_application_submitted(
        application_id="app_123", user_id="user_456", job_count=5
    )

    # Assert
    publisher.publish.assert_awaited_once()
    call_args = publisher.publish.call_args
    payload = call_args[0][0]

    assert payload["event"] == "application.submitted"
    assert payload["application_id"] == "app_123"
    assert payload["user_id"] == "user_456"
    assert payload["job_count"] == 5
    assert payload["status"] == "pending"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_publish_status_changed():
    """Test publishing status changed notification."""
    # Arrange
    publisher = NotificationPublisher()
    publisher.publish = AsyncMock()

    # Act
    await publisher.publish_status_changed(
        application_id="app_123",
        user_id="user_456",
        status="processing",
        job_count=5,
        previous_status="pending",
    )

    # Assert
    publisher.publish.assert_awaited_once()
    call_args = publisher.publish.call_args
    payload = call_args[0][0]

    assert payload["event"] == "application.status_changed"
    assert payload["status"] == "processing"
    assert payload["previous_status"] == "pending"


@pytest.mark.asyncio
async def test_publish_status_changed_with_error():
    """Test publishing status changed notification with error reason."""
    # Arrange
    publisher = NotificationPublisher()
    publisher.publish = AsyncMock()

    # Act
    await publisher.publish_status_changed(
        application_id="app_123",
        user_id="user_456",
        status="failed",
        job_count=5,
        previous_status="processing",
        error_reason="Connection timeout",
    )

    # Assert
    publisher.publish.assert_awaited_once()
    call_args = publisher.publish.call_args
    payload = call_args[0][0]

    assert payload["status"] == "failed"
    assert payload["error_reason"] == "Connection timeout"


@pytest.mark.asyncio
async def test_build_event_payload():
    """Test the event payload structure."""
    # Arrange
    publisher = NotificationPublisher()

    # Act
    payload = publisher._build_event_payload(
        event="test.event",
        application_id="app_123",
        user_id="user_456",
        status="pending",
        job_count=3,
    )

    # Assert
    assert payload["event"] == "test.event"
    assert payload["version"] == "1.0"
    assert payload["application_id"] == "app_123"
    assert payload["user_id"] == "user_456"
    assert payload["status"] == "pending"
    assert payload["job_count"] == 3
    assert "timestamp" in payload
    assert payload["timestamp"].endswith("Z")
