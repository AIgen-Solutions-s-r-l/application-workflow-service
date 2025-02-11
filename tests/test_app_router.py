import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import json
from app.main import app
from app.core.auth import get_current_user

TEST_USER_ID = "test_user_123"

async def mock_get_current_user():
    return TEST_USER_ID

app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def mock_mongo():
    with patch('app.routers.app_router.mongo_client') as mock:
        mock_collection = AsyncMock()
        mock_db = MagicMock()
        mock_db.get_collection.return_value = mock_collection
        mock.get_database.return_value = mock_db
        yield mock

@pytest.mark.asyncio
async def test_submit_jobs_and_save_application(test_client, mock_mongo):
    test_jobs = [
        {
            "job_id": 12345,
            "description": "Test job description",
            "portal": "LinkedIn",
            "title": "Software Engineer"
        }
    ]
    with patch('app.services.application_uploader_service.ApplicationUploaderService.insert_application_jobs') as mock_insert:
        mock_insert.return_value = "some_mocked_object_id"
        jobs_payload = json.dumps({"jobs": test_jobs})
        response = test_client.post(
            "/applications",
            data={"jobs": jobs_payload},
            files={}
        )
        assert response.status_code == 200
        assert response.json() is True
        mock_insert.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_successful_applications(test_client, mock_mongo):
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn"
            }
        }
    }
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    response = test_client.get("/applied")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "app1" in data
    app_data = data["app1"]
    assert app_data["title"] == "Software Engineer"
    assert app_data["description"] == "Test job description"
    assert app_data["portal"] == "LinkedIn"

@pytest.mark.asyncio
async def test_get_successful_application_details(test_client, mock_mongo):
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "resume_optimized": json.dumps({"text": "test resume"}),
                "cover_letter": json.dumps({"text": "test cover letter"})
            }
        }
    }
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    response = test_client.get(f"/applied/{app_id}")
    assert response.status_code == 200
    detail_data = response.json()
    assert isinstance(detail_data["resume_optimized"], dict)
    assert detail_data["resume_optimized"]["text"] == "test resume"
    assert isinstance(detail_data["cover_letter"], dict)
    assert detail_data["cover_letter"]["text"] == "test cover letter"

@pytest.mark.asyncio
async def test_get_failed_applications(test_client, mock_mongo):
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "title": "Failed Application",
                "description": "Test job description",
                "portal": "Indeed"
            }
        }
    }
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    response = test_client.get("/fail_applied")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "app1" in data
    app_data = data["app1"]
    assert app_data["title"] == "Failed Application"
    assert app_data["description"] == "Test job description"
    assert app_data["portal"] == "Indeed"

@pytest.mark.asyncio
async def test_get_failed_application_details(test_client, mock_mongo):
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "resume_optimized": json.dumps({"text": "test resume"}),
                "cover_letter": json.dumps({"text": "test cover letter"})
            }
        }
    }
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    response = test_client.get(f"/fail_applied/{app_id}")
    assert response.status_code == 200
    detail_data = response.json()
    assert isinstance(detail_data["resume_optimized"], dict)
    assert detail_data["resume_optimized"]["text"] == "test resume"
    assert isinstance(detail_data["cover_letter"], dict)
    assert detail_data["cover_letter"]["text"] == "test cover letter"

@pytest.mark.asyncio
async def test_application_not_found(test_client, mock_mongo):
    mock_mongo.get_database().get_collection().find_one.return_value = None
    response = test_client.get("/applied")
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "No applications found" in response.json()["detail"]
    response = test_client.get("/fail_applied")
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "No applications found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_application_detail_not_found(test_client, mock_mongo):
    app_id = "nonexistent"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "another_app_id": {
                "resume_optimized": json.dumps({"text": "some-other"}),
                "cover_letter": json.dumps({"text": "some-other-cover"})
            }
        }
    }
    mock_mongo.get_database().get_collection().find_one.return_value = mock_doc
    response = test_client.get(f"/applied/{app_id}")
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Application ID not found" in response.json()["detail"]
    response = test_client.get(f"/fail_applied/{app_id}")
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Application ID not found" in response.json()["detail"]
