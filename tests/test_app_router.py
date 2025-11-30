"""Legacy test file for app router - tests migrated to tests/routers/."""

import json

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.auth import get_current_user
from app.main import app

TEST_USER_ID = "test_user_123"


async def mock_get_current_user():
    return TEST_USER_ID


app.dependency_overrides[get_current_user] = mock_get_current_user


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_submit_jobs_and_save_application(test_client):
    """Test successful job submission."""
    test_jobs = [
        {
            "job_id": 12345,
            "description": "Test job description",
            "portal": "LinkedIn",
            "title": "Software Engineer",
        }
    ]

    mock_app_uploader = MagicMock()
    mock_app_uploader.insert_application_jobs = AsyncMock(return_value="mocked_app_id")

    with patch("app.routers.app_router.application_uploader", mock_app_uploader):
        jobs_payload = json.dumps({"jobs": test_jobs})
        response = test_client.post(
            "/applications",
            data={"jobs": jobs_payload},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "mocked_app_id"
        assert data["status"] == "pending"
        mock_app_uploader.insert_application_jobs.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_successful_applications(test_client):
    """Test retrieving successful applications with pagination."""
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn",
            }
        },
    }

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=mock_doc)

    with patch(
        "app.routers.app_router.success_applications_collection", mock_collection
    ):
        response = test_client.get("/applied")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert "app1" in data["data"]
        app_data = data["data"]["app1"]
        assert app_data["title"] == "Software Engineer"
        assert app_data["description"] == "Test job description"
        assert app_data["portal"] == "LinkedIn"


@pytest.mark.asyncio
async def test_get_successful_application_details(test_client):
    """Test retrieving details for a specific successful application."""
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "resume_optimized": json.dumps({"text": "test resume"}),
                "cover_letter": json.dumps({"text": "test cover letter"}),
            }
        },
    }

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=mock_doc)

    with patch(
        "app.routers.app_router.success_applications_collection", mock_collection
    ):
        response = test_client.get(f"/applied/{app_id}")
        assert response.status_code == 200
        detail_data = response.json()
        assert isinstance(detail_data["resume_optimized"], dict)
        assert detail_data["resume_optimized"]["text"] == "test resume"
        assert isinstance(detail_data["cover_letter"], dict)
        assert detail_data["cover_letter"]["text"] == "test cover letter"


@pytest.mark.asyncio
async def test_get_failed_applications(test_client):
    """Test retrieving failed applications with pagination."""
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "title": "Failed Application",
                "description": "Test job description",
                "portal": "Indeed",
            }
        },
    }

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=mock_doc)

    with patch(
        "app.routers.app_router.failed_applications_collection", mock_collection
    ):
        response = test_client.get("/fail_applied")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert "app1" in data["data"]
        app_data = data["data"]["app1"]
        assert app_data["title"] == "Failed Application"
        assert app_data["description"] == "Test job description"
        assert app_data["portal"] == "Indeed"


@pytest.mark.asyncio
async def test_get_failed_application_details(test_client):
    """Test retrieving details for a specific failed application."""
    app_id = "app1"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            app_id: {
                "resume_optimized": json.dumps({"text": "test resume"}),
                "cover_letter": json.dumps({"text": "test cover letter"}),
            }
        },
    }

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=mock_doc)

    with patch(
        "app.routers.app_router.failed_applications_collection", mock_collection
    ):
        response = test_client.get(f"/fail_applied/{app_id}")
        assert response.status_code == 200
        detail_data = response.json()
        assert isinstance(detail_data["resume_optimized"], dict)
        assert detail_data["resume_optimized"]["text"] == "test resume"
        assert isinstance(detail_data["cover_letter"], dict)
        assert detail_data["cover_letter"]["text"] == "test cover letter"


@pytest.mark.asyncio
async def test_application_not_found(test_client):
    """Test handling when no applications found (returns empty data, not error)."""
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    with patch(
        "app.routers.app_router.success_applications_collection", mock_collection
    ):
        response = test_client.get("/applied")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == {}
        assert data["pagination"]["has_more"] is False

    with patch(
        "app.routers.app_router.failed_applications_collection", mock_collection
    ):
        response = test_client.get("/fail_applied")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == {}
        assert data["pagination"]["has_more"] is False


@pytest.mark.asyncio
async def test_application_detail_not_found(test_client):
    """Test handling when a specific application is not found."""
    app_id = "nonexistent"
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "another_app_id": {
                "resume_optimized": json.dumps({"text": "some-other"}),
                "cover_letter": json.dumps({"text": "some-other-cover"}),
            }
        },
    }

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=mock_doc)

    with patch(
        "app.routers.app_router.success_applications_collection", mock_collection
    ):
        response = test_client.get(f"/applied/{app_id}")
        assert response.status_code == 404
        assert "detail" in response.json()
        assert "Application ID not found" in response.json()["detail"]

    with patch(
        "app.routers.app_router.failed_applications_collection", mock_collection
    ):
        response = test_client.get(f"/fail_applied/{app_id}")
        assert response.status_code == 404
        assert "detail" in response.json()
        assert "Application ID not found" in response.json()["detail"]
