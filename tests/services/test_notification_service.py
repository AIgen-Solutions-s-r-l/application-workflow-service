import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.notification_service import NotificationPublisher
from app.services.base_publisher import BasePublisher

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
    
    with patch('app.services.notification_service.settings', mock_settings):
        publisher = NotificationPublisher()
        
        # Act
        result = publisher.get_queue_name()
        
        # Assert
        assert result == "test_middleware_queue"

@pytest.mark.asyncio
async def test_publish_application_updated():
    """Test publishing an application updated notification."""
    # Arrange
    publisher = NotificationPublisher()
    publisher.publish = AsyncMock()
    
    # Act
    await publisher.publish_application_updated()
    
    # Assert
    publisher.publish.assert_awaited_once_with({"updated": True}, False)

@pytest.mark.asyncio
async def test_publish_application_updated_with_logger():
    """Test that logging occurs when publishing."""
    # Arrange
    publisher = NotificationPublisher()
    publisher.publish = AsyncMock()
    
    with patch('app.services.notification_service.logger') as mock_logger:
        # Act
        await publisher.publish_application_updated()
        
        # Assert
        mock_logger.info.assert_called_once()
        assert "Publishing notification about application update" in mock_logger.info.call_args[0][0]
        assert mock_logger.info.call_args[1]["event_type"] == "notification_publishing"
        publisher.publish.assert_awaited_once_with({"updated": True}, False)