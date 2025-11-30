"""Tests for application submission endpoints."""

import json

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.auth import get_current_user
from app.core.exceptions import DatabaseOperationError
from app.main import app

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
async def test_submit_jobs_success(test_client):
    """Test successful submission of job applications without PDF."""
    # Arrange
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn",
        }
    ]

    mock_app_uploader = MagicMock()
    mock_app_uploader.insert_application_jobs = AsyncMock(return_value="mocked_app_id")

    with patch("app.routers.app_router.application_uploader", mock_app_uploader):
        # Act
        jobs_payload = json.dumps({"jobs": test_jobs})
        response = test_client.post("/applications", data={"jobs": jobs_payload})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "mocked_app_id"
        assert data["status"] == "pending"
        assert data["job_count"] == 1
        assert "status_url" in data
        assert data["status_url"] == "/applications/mocked_app_id/status"
        assert "created_at" in data

        mock_app_uploader.insert_application_jobs.assert_awaited_once()
        call_args = mock_app_uploader.insert_application_jobs.call_args
        assert call_args.kwargs["user_id"] == TEST_USER_ID
        assert len(call_args.kwargs["job_list_to_apply"]) == 1
        assert call_args.kwargs["job_list_to_apply"][0]["title"] == "Software Engineer"
        assert call_args.kwargs["cv_id"] is None
        assert call_args.kwargs["style"] is None


@pytest.mark.asyncio
async def test_submit_jobs_with_style(test_client):
    """Test submission with a style parameter."""
    # Arrange
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn",
        }
    ]

    mock_app_uploader = MagicMock()
    mock_app_uploader.insert_application_jobs = AsyncMock(return_value="mocked_app_id")

    with patch("app.routers.app_router.application_uploader", mock_app_uploader):
        # Act
        jobs_payload = json.dumps({"jobs": test_jobs})
        response = test_client.post(
            "/applications", data={"jobs": jobs_payload, "style": "professional"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "mocked_app_id"
        assert data["status"] == "pending"
        assert data["job_count"] == 1

        mock_app_uploader.insert_application_jobs.assert_awaited_once()
        call_args = mock_app_uploader.insert_application_jobs.call_args
        assert call_args.kwargs["style"] == "professional"


@pytest.mark.asyncio
async def test_submit_jobs_with_pdf(test_client):
    """Test submission with a PDF resume."""
    # Arrange
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn",
        }
    ]

    mock_pdf_service = MagicMock()
    mock_pdf_service.store_pdf_resume = AsyncMock(return_value="mocked_pdf_id")

    mock_app_uploader = MagicMock()
    mock_app_uploader.insert_application_jobs = AsyncMock(return_value="mocked_app_id")

    with patch("app.routers.app_router.pdf_resume_service", mock_pdf_service), patch(
        "app.routers.app_router.application_uploader", mock_app_uploader
    ):
        # Act
        jobs_payload = json.dumps({"jobs": test_jobs})
        pdf_content = b"%PDF-1.5\nTest PDF content"

        response = test_client.post(
            "/applications",
            data={"jobs": jobs_payload},
            files={"cv": ("resume.pdf", pdf_content, "application/pdf")},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "mocked_app_id"
        assert data["status"] == "pending"
        assert data["job_count"] == 1

        mock_pdf_service.store_pdf_resume.assert_awaited_once()
        mock_app_uploader.insert_application_jobs.assert_awaited_once()

        # Check CV ID is passed correctly
        call_args = mock_app_uploader.insert_application_jobs.call_args
        assert call_args.kwargs["cv_id"] == "mocked_pdf_id"


@pytest.mark.asyncio
async def test_submit_jobs_invalid_json(test_client):
    """Test handling invalid JSON data."""
    # Arrange & Act
    response = test_client.post(
        "/applications", data={"jobs": "this is not valid JSON"}
    )

    # Assert
    # Updated to expect 422 (Unprocessable Entity) instead of 400 (Bad Request)
    # because FastAPI uses 422 for request validation errors
    assert response.status_code == 422
    assert "Invalid jobs data" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_jobs_validation_error(test_client):
    """Test handling validation errors in job data."""
    # Arrange
    # Missing required 'jobs' field
    invalid_payload = json.dumps({"not_jobs": []})

    # Act
    response = test_client.post("/applications", data={"jobs": invalid_payload})

    # Assert
    assert response.status_code == 422
    assert "Invalid jobs data" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_jobs_invalid_pdf_type(test_client):
    """Test handling non-PDF file uploads."""
    # Arrange
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn",
        }
    ]

    # Act
    jobs_payload = json.dumps({"jobs": test_jobs})
    not_pdf_content = b"This is not a PDF file"

    response = test_client.post(
        "/applications",
        data={"jobs": jobs_payload},
        files={"cv": ("resume.txt", not_pdf_content, "text/plain")},
    )

    # Assert
    assert response.status_code == 400
    assert "Uploaded file must be a PDF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_jobs_pdf_storage_error(test_client):
    """Test handling errors when storing PDF."""
    # Arrange
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn",
        }
    ]

    mock_pdf_service = MagicMock()
    mock_pdf_service.store_pdf_resume = AsyncMock(
        side_effect=DatabaseOperationError("PDF storage error")
    )

    with patch("app.routers.app_router.pdf_resume_service", mock_pdf_service):
        # Act
        jobs_payload = json.dumps({"jobs": test_jobs})
        pdf_content = b"%PDF-1.5\nTest PDF content"

        response = test_client.post(
            "/applications",
            data={"jobs": jobs_payload},
            files={"cv": ("resume.pdf", pdf_content, "application/pdf")},
        )

        # Assert
        assert response.status_code == 500
        assert "Failed to store PDF resume" in response.json()["detail"]
        assert "PDF storage error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_jobs_application_storage_error(test_client):
    """Test handling errors when storing application data."""
    # Arrange
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn",
        }
    ]

    mock_app_uploader = MagicMock()
    mock_app_uploader.insert_application_jobs = AsyncMock(
        side_effect=DatabaseOperationError("Application storage error")
    )

    with patch("app.routers.app_router.application_uploader", mock_app_uploader):
        # Act
        jobs_payload = json.dumps({"jobs": test_jobs})

        response = test_client.post("/applications", data={"jobs": jobs_payload})

        # Assert
        assert response.status_code == 500
        assert "Failed to save application" in response.json()["detail"]
        assert "Application storage error" in response.json()["detail"]
