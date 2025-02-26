import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import io

from app.main import app
from app.core.auth import get_current_user

# Mock authentication for tests
TEST_USER_ID = "test_user_flow"

async def mock_get_current_user():
    return TEST_USER_ID

# Override the auth dependency for tests
app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def test_client():
    """Create a test client for FastAPI."""
    return TestClient(app)

@pytest.mark.asyncio
async def test_full_application_flow():
    """
    Test the full flow of submitting an application and retrieving it.
    
    This integration test verifies that:
    1. An application can be submitted with a PDF
    2. The PDF is stored in the right collection
    3. The application data is stored correctly
    4. The application can be retrieved from the success_app collection
    5. The application details can be retrieved
    """
    # Arrange
    client = TestClient(app)
    
    # Mock the PDF resume collection
    mock_pdf_collection = AsyncMock()
    mock_pdf_id = "test_pdf_id_12345"
    mock_pdf_collection.insert_one.return_value.inserted_id = mock_pdf_id
    
    # Mock the applications collection
    mock_app_collection = AsyncMock()
    mock_app_id = "test_app_id_67890"
    mock_app_collection.insert_one.return_value.inserted_id = mock_app_id
    
    # Mock the success_app collection for retrieval
    mock_success_app = {
        "user_id": TEST_USER_ID,
        "content": {
            mock_app_id: {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn",
                "resume_optimized": json.dumps({"text": "optimized resume"}),
                "cover_letter": json.dumps({"text": "generated cover letter"})
            }
        }
    }
    
    # Setup test data
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn"
        }
    ]
    
    # Create mocks for all database operations
    with patch('app.services.pdf_resume_service.pdf_resumes_collection', mock_pdf_collection), \
         patch('app.services.application_uploader_service.applications_collection', mock_app_collection), \
         patch('app.services.application_uploader_service.notification_publisher', AsyncMock()), \
         patch('app.routers.app_router.mongo_client') as mock_mongo:
        
        # Configure mongo client for retrieval
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = mock_success_app
        mock_db.get_collection.return_value = mock_collection
        mock_mongo.get_database.return_value = mock_db
        
        # STEP 1: Submit the application with a PDF
        jobs_payload = json.dumps({"jobs": test_jobs})
        pdf_content = b"%PDF-1.5\nTest PDF content"
        
        submit_response = client.post(
            "/applications",
            data={"jobs": jobs_payload, "style": "professional"},
            files={"cv": ("resume.pdf", pdf_content, "application/pdf")}
        )
        
        # Verify the submission was successful
        assert submit_response.status_code == 200
        assert submit_response.json() is True
        
        # Verify the PDF was stored correctly
        mock_pdf_collection.insert_one.assert_called_once()
        pdf_call_args = mock_pdf_collection.insert_one.call_args[0][0]
        assert pdf_call_args["cv"] == pdf_content
        assert pdf_call_args["app_ids"] == []
        
        # Verify the application was stored correctly
        mock_app_collection.insert_one.assert_called_once()
        app_call_args = mock_app_collection.insert_one.call_args[0][0]
        assert app_call_args["user_id"] == TEST_USER_ID
        assert app_call_args["cv_id"] == mock_pdf_id
        assert app_call_args["style"] == "professional"
        assert len(app_call_args["jobs"]) == 1
        assert app_call_args["jobs"][0]["title"] == "Software Engineer"
        assert app_call_args["jobs"][0]["gen_cv"] is False  # Should be False when CV is provided
        
        # STEP 2: Retrieve the list of successful applications
        list_response = client.get("/applied")
        
        # Verify the list retrieval was successful
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert isinstance(list_data, dict)
        assert mock_app_id in list_data
        assert list_data[mock_app_id]["title"] == "Software Engineer"
        
        # STEP 3: Retrieve the detailed application information
        detail_response = client.get(f"/applied/{mock_app_id}")
        
        # Verify the detail retrieval was successful
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        assert "resume_optimized" in detail_data
        assert "cover_letter" in detail_data
        assert detail_data["resume_optimized"]["text"] == "optimized resume"
        assert detail_data["cover_letter"]["text"] == "generated cover letter"

@pytest.mark.asyncio
async def test_application_failure_handling():
    """
    Test handling of failures in the application submission process.
    
    This integration test verifies that:
    1. If PDF storage fails, the application is not processed
    2. If application storage fails, an appropriate error is returned
    3. Error responses include useful information
    """
    # Arrange
    client = TestClient(app)
    
    # Setup test data
    test_jobs = [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn"
        }
    ]
    
    # Scenario 1: PDF storage fails
    with patch('app.services.pdf_resume_service.pdf_resumes_collection') as mock_pdf_collection:
        # Configure the mock to raise an exception
        mock_pdf_collection.insert_one.side_effect = Exception("Database connection error")
        
        # Submit an application with a PDF
        jobs_payload = json.dumps({"jobs": test_jobs})
        pdf_content = b"%PDF-1.5\nTest PDF content"
        
        response = client.post(
            "/applications",
            data={"jobs": jobs_payload},
            files={"cv": ("resume.pdf", pdf_content, "application/pdf")}
        )
        
        # Verify the error handling
        assert response.status_code == 500
        assert "Failed to store PDF resume" in response.json()["detail"]
        assert "Database connection error" in response.json()["detail"]
    
    # Scenario 2: Application storage fails
    with patch('app.services.pdf_resume_service.pdf_resumes_collection') as mock_pdf_collection, \
         patch('app.services.application_uploader_service.applications_collection') as mock_app_collection:
        
        # Configure PDF mock to succeed
        mock_pdf_id = "test_pdf_id_success"
        mock_pdf_collection.insert_one.return_value.inserted_id = mock_pdf_id
        
        # Configure application mock to fail
        mock_app_collection.insert_one.side_effect = Exception("Transaction failed")
        
        # Submit an application with a PDF
        jobs_payload = json.dumps({"jobs": test_jobs})
        pdf_content = b"%PDF-1.5\nTest PDF content"
        
        response = client.post(
            "/applications",
            data={"jobs": jobs_payload},
            files={"cv": ("resume.pdf", pdf_content, "application/pdf")}
        )
        
        # Verify the error handling
        assert response.status_code == 500
        assert "Failed to save application" in response.json()["detail"]
        assert "Transaction failed" in response.json()["detail"]
        
        # Verify the PDF was stored
        mock_pdf_collection.insert_one.assert_called_once()