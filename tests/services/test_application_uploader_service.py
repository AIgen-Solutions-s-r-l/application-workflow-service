import pytest
from unittest.mock import AsyncMock, patch
from app.services.application_uploader_service import ApplicationUploaderService
from app.core.exceptions import DatabaseOperationError

@pytest.mark.asyncio
async def test_insert_application_jobs_success(mock_applications_collection, mock_notification_publisher):
    """Test successful insertion of application jobs."""
    # Arrange
    service = ApplicationUploaderService()
    user_id = "test_user"
    job_list = [{"title": "Software Engineer", "description": "Test job"}]
    
    # Configure the mock to properly handle await
    mock_applications_collection.insert_one = AsyncMock()
    mock_applications_collection.insert_one.return_value.inserted_id = "mocked_application_id"
    
    # Act
    result = await service.insert_application_jobs(user_id, job_list)
    
    # Assert
    assert result == "mocked_application_id"
    mock_applications_collection.insert_one.assert_called_once()
    
    # Verify the document structure
    called_doc = mock_applications_collection.insert_one.call_args[0][0]
    assert called_doc["user_id"] == user_id
    assert called_doc["jobs"] == job_list
    assert called_doc["sent"] is False
    assert called_doc["retries_left"] == 5
    assert "cv_id" in called_doc
    assert called_doc["cv_id"] is None
    assert "style" in called_doc
    assert called_doc["style"] is None
    
    # Verify notification was published
    mock_notification_publisher.publish_application_updated.assert_awaited_once()

@pytest.mark.asyncio
async def test_insert_application_jobs_with_cv(mock_applications_collection, mock_notification_publisher):
    """Test insertion of application jobs with a CV ID."""
    # Arrange
    service = ApplicationUploaderService()
    user_id = "test_user"
    job_list = [{"title": "Software Engineer", "description": "Test job"}]
    cv_id = "test_cv_id"
    
    # Configure the mock to properly handle await
    mock_applications_collection.insert_one = AsyncMock()
    mock_applications_collection.insert_one.return_value.inserted_id = "mocked_application_id"
    
    # Act
    result = await service.insert_application_jobs(user_id, job_list, cv_id=cv_id)
    
    # Assert
    assert result == "mocked_application_id"
    mock_applications_collection.insert_one.assert_called_once()
    
    # Verify the document structure
    called_doc = mock_applications_collection.insert_one.call_args[0][0]
    assert called_doc["user_id"] == user_id
    assert len(called_doc["jobs"]) == 1
    assert called_doc["jobs"][0]["gen_cv"] is False  # gen_cv should be False when cv_id is provided
    assert called_doc["cv_id"] == cv_id
    
    # Verify notification was published
    mock_notification_publisher.publish_application_updated.assert_awaited_once()

@pytest.mark.asyncio
async def test_insert_application_jobs_with_style(mock_applications_collection, mock_notification_publisher):
    """Test insertion of application jobs with a style parameter."""
    # Arrange
    service = ApplicationUploaderService()
    user_id = "test_user"
    job_list = [{"title": "Software Engineer", "description": "Test job"}]
    style = "professional"
    
    # Configure the mock to properly handle await
    mock_applications_collection.insert_one = AsyncMock()
    mock_applications_collection.insert_one.return_value.inserted_id = "mocked_application_id"
    
    # Act
    result = await service.insert_application_jobs(user_id, job_list, style=style)
    
    # Assert
    assert result == "mocked_application_id"
    mock_applications_collection.insert_one.assert_called_once()
    
    # Verify the document structure
    called_doc = mock_applications_collection.insert_one.call_args[0][0]
    assert called_doc["style"] == style
    
    # Verify notification was published
    mock_notification_publisher.publish_application_updated.assert_awaited_once()

@pytest.mark.asyncio
async def test_insert_application_jobs_database_error(mock_applications_collection):
    """Test error handling when database operation fails."""
    # Arrange
    # Configure the mock to properly handle await and raise an exception
    mock_applications_collection.insert_one = AsyncMock(side_effect=Exception("Database error"))
    
    service = ApplicationUploaderService()
    user_id = "test_user"
    job_list = [{"title": "Software Engineer", "description": "Test job"}]
    
    # Act & Assert
    with pytest.raises(DatabaseOperationError) as exc_info:
        await service.insert_application_jobs(user_id, job_list)
    
    # Verify error message
    assert "Error upserting application data" in str(exc_info.value)
    assert "Database error" in str(exc_info.value)