import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException
from app.main import app
from app.schemas.app_jobs import JobApplicationRequest, JobData, DetailedJobData
from app.routers.app_router import router, mongo_client
from app.core.auth import get_current_user

# Mock user for testing
TEST_USER_ID = "test_user_123"

# Mock authentication dependency
async def mock_get_current_user():
    return TEST_USER_ID

# Override the dependency at the app level
app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def mock_mongo():
    with patch('app.routers.app_router.mongo_client') as mock:
        # Setup mock database and collection
        mock_collection = AsyncMock()
        mock_db = MagicMock()
        mock_db.get_collection.return_value = mock_collection
        mock.get_database.return_value = mock_db
        yield mock

@pytest.mark.asyncio
async def test_submit_jobs_and_save_application(test_client, mock_mongo):
    # Mock data matching JobItem schema
    test_jobs = [{
        "job_id": 12345,
        "description": "Test job description",
        "portal": "LinkedIn",
        "title": "Software Engineer"
    }]
    
    # Mock upsert response
    mock_app_id = ObjectId()  # Create ObjectId first
    with patch('app.services.resume_ops.upsert_application_jobs', return_value=mock_app_id):
        response = test_client.post(
            "/applications",
            json={"jobs": test_jobs}
        )
        
        assert response.status_code == 200
        assert "application_id" in response.json()
        # The router returns either the application_id or "Updated applications"
        assert response.json()["application_id"] in [str(mock_app_id), "Updated applications"]

@pytest.mark.asyncio
async def test_get_successful_applications(test_client, mock_mongo):
    # Mock successful applications data matching JobData schema
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "job_id": 12345,
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn"
            }
        }
    }
    
    # Setup mock find_one response
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    
    response = test_client.get("/applied")
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Software Engineer"

@pytest.mark.asyncio
async def test_get_successful_application_details(test_client, mock_mongo):
    app_id = "app1"
    # Mock data matching DetailedJobData schema
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "resume_optimized": "test resume",
                "cover_letter": "test cover letter"
            }
        }
    }
    
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    
    response = test_client.get(f"/applied/{app_id}")
    
    assert response.status_code == 200
    assert "resume_optimized" in response.json()
    assert "cover_letter" in response.json()

@pytest.mark.asyncio
async def test_get_failed_applications(test_client, mock_mongo):
    # Mock failed applications data matching JobData schema
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "job_id": 12345,
                "title": "Failed Application",
                "description": "Test job description",
                "portal": "LinkedIn"
            }
        }
    }
    
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    
    response = test_client.get("/fail_applied")
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Failed Application"

@pytest.mark.asyncio
async def test_get_failed_application_details(test_client, mock_mongo):
    app_id = "app1"
    # Mock data matching DetailedJobData schema
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "resume_optimized": "test resume",
                "cover_letter": "test cover letter"
            }
        }
    }
    
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    
    response = test_client.get(f"/fail_applied/{app_id}")
    
    assert response.status_code == 200
    assert "resume_optimized" in response.json()
    assert "cover_letter" in response.json()

@pytest.mark.asyncio
async def test_application_not_found(test_client, mock_mongo):
    # Mock empty response from MongoDB
    mock_mongo.get_database().get_collection().find_one.return_value = None
    
    response = test_client.get("/applied")
    assert response.status_code == 500  # Router converts 404 to 500
    assert "detail" in response.json()
    assert "Failed to fetch" in response.json()["detail"]
    
    response = test_client.get("/fail_applied")
    assert response.status_code == 500  # Router converts 404 to 500
    assert "detail" in response.json()
    assert "Failed to fetch" in response.json()["detail"]

@pytest.mark.asyncio
async def test_application_detail_not_found(test_client, mock_mongo):
    app_id = "nonexistent"
    # Mock document with empty content
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {}
    }
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    
    response = test_client.get(f"/applied/{app_id}")
    assert response.status_code == 500  # Router converts 404 to 500
    assert "detail" in response.json()
    assert "Failed to fetch" in response.json()["detail"]
    
    response = test_client.get(f"/fail_applied/{app_id}")
    assert response.status_code == 500  # Router converts 404 to 500
    assert "detail" in response.json()
    assert "Failed to fetch" in response.json()["detail"]