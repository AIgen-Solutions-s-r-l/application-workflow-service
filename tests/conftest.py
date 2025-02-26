import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.main import app
from app.core.auth import get_current_user

# Constants for testing
TEST_USER_ID = "test_user_123"

# Auth fixtures
async def mock_get_current_user():
    """Mock the authentication to always return a test user ID."""
    return TEST_USER_ID

@pytest.fixture
def test_client():
    """Create a test client for FastAPI with authentication mocked."""
    # Override the dependency for authentication
    app.dependency_overrides[get_current_user] = mock_get_current_user
    client = TestClient(app)
    
    yield client
    
    # Clean up after test
    app.dependency_overrides.clear()

# MongoDB Fixtures
@pytest.fixture
def mock_mongo_client():
    """Mock the MongoDB client for testing."""
    with patch('app.core.mongo.AsyncIOMotorClient') as mock:
        mock_client = MagicMock(spec=AsyncIOMotorClient)
        mock_db = MagicMock(spec=AsyncIOMotorDatabase)
        mock_collection = AsyncMock(spec=AsyncIOMotorCollection)
        
        # Important: Use MagicMock for synchronous methods and AsyncMock for async methods
        mock_client.get_database = MagicMock(return_value=mock_db)
        mock_db.get_collection = MagicMock(return_value=mock_collection)
        
        mock.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_applications_collection():
    """Mock the applications collection."""
    with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
        # Don't set insert_one here - let each test configure it
        # This allows tests to properly set up AsyncMock
        yield mock_collection

@pytest.fixture
def mock_pdf_resumes_collection():
    """Mock the PDF resumes collection."""
    with patch('app.services.pdf_resume_service.pdf_resumes_collection') as mock_collection:
        # Don't set insert_one here - let each test configure it
        # This allows tests to properly set up AsyncMock
        yield mock_collection

# RabbitMQ Fixtures
@pytest.fixture
def mock_rabbitmq_client():
    """Mock the RabbitMQ client for testing."""
    with patch('app.core.rabbitmq_client.aio_pika.connect_robust') as mock_connect:
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        mock_exchange = AsyncMock()
        
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.return_value = mock_queue
        mock_channel.default_exchange = mock_exchange
        mock_connect.return_value = mock_connection
        
        yield mock_connect, mock_connection, mock_channel, mock_queue, mock_exchange

@pytest.fixture
def mock_notification_publisher():
    """Mock the notification publisher."""
    with patch('app.services.application_uploader_service.notification_publisher') as mock_publisher:
        mock_publisher.publish_application_updated = AsyncMock()
        yield mock_publisher

# Test Data Fixtures
@pytest.fixture
def sample_job_data():
    """Provide sample job data for tests."""
    return {
        "title": "Software Engineer",
        "description": "Test job description",
        "portal": "LinkedIn",
        "workplace_type": "Remote",
        "job_state": "Open",
        "company_name": "Test Company"
    }

@pytest.fixture
def sample_job_list():
    """Provide a sample list of jobs for tests."""
    return [
        {
            "title": "Software Engineer",
            "description": "Test job description",
            "portal": "LinkedIn"
        },
        {
            "title": "Data Scientist",
            "description": "Data science position",
            "portal": "Indeed"
        }
    ]

@pytest.fixture
def sample_pdf_bytes():
    """Provide sample PDF bytes for testing."""
    return b"%PDF-1.5\nTest PDF content"