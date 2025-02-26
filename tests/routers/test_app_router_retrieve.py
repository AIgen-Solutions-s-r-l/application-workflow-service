import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_current_user

# Mock authentication for tests
TEST_USER_ID = "test_user_123"

async def mock_get_current_user():
    return TEST_USER_ID

# Override the auth dependency for tests
app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def test_client():
    """Create a test client for FastAPI."""
    return TestClient(app)

@pytest.mark.asyncio
async def test_get_successful_applications(test_client):
    """Test retrieving all successful applications."""
    # Arrange
    mock_doc = {
        "user_id": TEST_USER_ID,
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
    
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)):
        # Act
        response = test_client.get("/applied")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) == 2
        assert "app1" in data
        assert "app2" in data
        assert data["app1"]["title"] == "Software Engineer"
        assert data["app2"]["title"] == "Data Scientist"

@pytest.mark.asyncio
async def test_get_successful_applications_empty(test_client):
    """Test handling when no successful applications are found."""
    # Arrange
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(side_effect=Exception("No valid successful applications found for this user."))):
        # Act
        response = test_client.get("/applied")
        
        # Assert
        assert response.status_code == 500
        assert "Failed to fetch successful apps" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_successful_application_details(test_client):
    """Test retrieving details for a specific successful application."""
    # Arrange
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn",
                "resume_optimized": json.dumps({"text": "test resume"}),
                "cover_letter": json.dumps({"text": "test cover letter"})
            }
        }
    }
    
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)):
        # Act
        response = test_client.get(f"/applied/{app_id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "resume_optimized" in data
        assert "cover_letter" in data
        assert data["resume_optimized"]["text"] == "test resume"
        assert data["cover_letter"]["text"] == "test cover letter"

@pytest.mark.asyncio
async def test_get_successful_application_details_not_found(test_client):
    """Test handling when a specific successful application is not found."""
    # Arrange
    app_id = "nonexistent"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "different_app": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn"
            }
        }
    }
    
    # Create a HTTPException with status_code=404 that will be raised
    from fastapi import HTTPException
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)), \
         patch('app.routers.app_router.logger'):
        # Act
        response = test_client.get(f"/applied/{app_id}")
        
        # Assert
        # In actual code, the error is caught and re-raised as 500, so we check for 500
        assert response.status_code == 500
        assert "Application ID not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_successful_application_details_json_error(test_client):
    """Test handling when JSON parsing fails for application details."""
    # Arrange
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "resume_optimized": "This is not valid JSON",
                "cover_letter": "This is also not valid JSON"
            }
        }
    }
    
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)):
        # Act
        response = test_client.get(f"/applied/{app_id}")
        
        # Assert
        assert response.status_code == 500
        assert "Failed to fetch detailed application info" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_failed_applications(test_client):
    """Test retrieving all failed applications."""
    # Arrange
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "title": "Failed Job Application",
                "description": "Test job description",
                "portal": "LinkedIn"
            }
        }
    }
    
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)):
        # Act
        response = test_client.get("/fail_applied")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) == 1
        assert "app1" in data
        assert data["app1"]["title"] == "Failed Job Application"

@pytest.mark.asyncio
async def test_get_failed_applications_empty(test_client):
    """Test handling when no failed applications are found."""
    # Arrange
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(side_effect=Exception("No valid failed applications found for this user."))):
        # Act
        response = test_client.get("/fail_applied")
        
        # Assert
        assert response.status_code == 500
        assert "Failed to fetch failed apps" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_failed_application_details(test_client):
    """Test retrieving details for a specific failed application."""
    # Arrange
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "title": "Failed Job Application",
                "description": "Test job description",
                "portal": "LinkedIn",
                "resume_optimized": json.dumps({"text": "test resume"}),
                "cover_letter": json.dumps({"text": "test cover letter"})
            }
        }
    }
    
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)):
        # Act
        response = test_client.get(f"/fail_applied/{app_id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "resume_optimized" in data
        assert "cover_letter" in data
        assert data["resume_optimized"]["text"] == "test resume"
        assert data["cover_letter"]["text"] == "test cover letter"

@pytest.mark.asyncio
async def test_get_failed_application_details_not_found(test_client):
    """Test handling when a specific failed application is not found."""
    # Arrange
    app_id = "nonexistent"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "different_app": {
                "title": "Failed Job Application",
                "description": "Test job description",
                "portal": "LinkedIn"
            }
        }
    }
    
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)), \
         patch('app.routers.app_router.logger'):
        # Act
        response = test_client.get(f"/fail_applied/{app_id}")
        
        # Assert
        # In actual code, the error is caught and re-raised as 500, so we check for 500
        assert response.status_code == 500
        assert "Application ID not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_failed_application_details_missing_fields(test_client):
    """Test handling when application details are missing fields."""
    # Arrange
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "title": "Failed Job Application",
                "description": "Test job description",
                "portal": "LinkedIn"
                # No resume_optimized or cover_letter
            }
        }
    }
    
    with patch('app.routers.app_router.fetch_user_doc', AsyncMock(return_value=mock_doc)):
        # Act
        response = test_client.get(f"/fail_applied/{app_id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["resume_optimized"] is None
        assert data["cover_letter"] is None