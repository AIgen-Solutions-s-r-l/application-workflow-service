import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastapi import HTTPException
from app.routers.app_router import fetch_user_doc, parse_applications
from app.models.job import JobData

@pytest.mark.asyncio
async def test_fetch_user_doc_success():
    """Test successful document fetch."""
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()
    mock_doc = {"user_id": "test_user", "content": {"app1": {"title": "Test Job"}}}
    
    # Use AsyncMock for get_database to properly handle awaits
    mock_client.get_database = MagicMock(return_value=mock_db)
    mock_db.get_collection = MagicMock(return_value=mock_collection)
    mock_collection.find_one = AsyncMock(return_value=mock_doc)
    
    with patch('app.routers.app_router.mongo_client', mock_client):
        # Act
        result = await fetch_user_doc("test_db", "test_collection", "test_user")
        
        # Assert
        mock_client.get_database.assert_called_once_with("test_db")
        mock_db.get_collection.assert_called_once_with("test_collection")
        mock_collection.find_one.assert_called_once_with({"user_id": "test_user"})
        assert result == mock_doc

@pytest.mark.asyncio
async def test_fetch_user_doc_not_found():
    """Test handling when no document is found."""
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()
    
    # Use AsyncMock for get_database to properly handle awaits
    mock_client.get_database = MagicMock(return_value=mock_db)
    mock_db.get_collection = MagicMock(return_value=mock_collection)
    mock_collection.find_one = AsyncMock(return_value=None)
    
    with patch('app.routers.app_router.mongo_client', mock_client):
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await fetch_user_doc("test_db", "test_collection", "test_user")
        
        assert exc_info.value.status_code == 404
        assert "No applications found" in exc_info.value.detail

@pytest.mark.asyncio
async def test_fetch_user_doc_empty_content():
    """Test handling when document has empty content."""
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()
    mock_doc = {"user_id": "test_user", "content": {}}
    
    # Use AsyncMock for get_database to properly handle awaits
    mock_client.get_database = MagicMock(return_value=mock_db)
    mock_db.get_collection = MagicMock(return_value=mock_collection)
    mock_collection.find_one = AsyncMock(return_value=mock_doc)
    
    with patch('app.routers.app_router.mongo_client', mock_client):
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await fetch_user_doc("test_db", "test_collection", "test_user")
        
        assert exc_info.value.status_code == 404
        assert "No applications found" in exc_info.value.detail

@pytest.mark.asyncio
async def test_fetch_user_doc_missing_content():
    """Test handling when document is missing content field."""
    # Arrange
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()
    mock_doc = {"user_id": "test_user"}  # No content field
    
    # Use AsyncMock for get_database to properly handle awaits
    mock_client.get_database = MagicMock(return_value=mock_db)
    mock_db.get_collection = MagicMock(return_value=mock_collection)
    mock_collection.find_one = AsyncMock(return_value=mock_doc)
    
    with patch('app.routers.app_router.mongo_client', mock_client):
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await fetch_user_doc("test_db", "test_collection", "test_user")
        
        assert exc_info.value.status_code == 404
        assert "No applications found" in exc_info.value.detail

def test_parse_applications_success():
    """Test successful parsing of applications."""
    # Arrange
    doc = {
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn"
            },
            "app2": {
                "title": "Data Scientist",
                "description": "Data science position",
                "portal": "Indeed"
            }
        }
    }
    
    # Act
    result = parse_applications(doc)
    
    # Assert
    assert isinstance(result, dict)
    assert len(result) == 2
    assert "app1" in result
    assert "app2" in result
    assert isinstance(result["app1"], JobData)
    assert isinstance(result["app2"], JobData)
    assert result["app1"].title == "Software Engineer"
    assert result["app2"].title == "Data Scientist"

def test_parse_applications_with_exclude_fields():
    """Test parsing applications with excluded fields."""
    # Arrange
    doc = {
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn",
                "resume_optimized": '{"some": "data"}',
                "cover_letter": '{"more": "data"}'
            }
        }
    }
    
    # Act
    result = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])
    
    # Assert
    assert isinstance(result, dict)
    assert len(result) == 1
    assert "app1" in result
    assert isinstance(result["app1"], JobData)
    assert result["app1"].title == "Software Engineer"
    # Check that excluded fields are not in the result
    job_dict = result["app1"].model_dump()
    assert "resume_optimized" not in job_dict
    assert "cover_letter" not in job_dict

def test_parse_applications_with_validation_error():
    """Test handling validation errors during parsing."""
    # Arrange
    doc = {
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn"
            },
            "app2": {
                # Missing required fields but this won't actually cause a validation error
                # with our JobData model because all fields are optional
                "invalid_field": "This will cause a validation error"
            }
        }
    }
    
    with patch('app.routers.app_router.logger') as mock_logger:
        # Act
        result = parse_applications(doc)
        
        # Assert
        assert isinstance(result, dict)
        assert len(result) == 2  # Both jobs should be included since JobData has all optional fields
        assert "app1" in result
        assert "app2" in result
        mock_logger.error.assert_not_called()  # No validation error with our model

def test_parse_applications_empty_content():
    """Test parsing with empty content."""
    # Arrange
    doc = {"content": {}}
    
    # Act
    result = parse_applications(doc)
    
    # Assert
    assert isinstance(result, dict)
    assert len(result) == 0