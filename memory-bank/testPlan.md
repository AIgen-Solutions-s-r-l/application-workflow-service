# Comprehensive Test Plan - Application Manager Service

## Objectives
- Create a comprehensive test suite for the critical components of the Application Manager Service
- Achieve at least 70% code coverage for critical parts
- Ensure functionality works as expected across different components

## Testing Approach

### 1. Unit Tests
Unit tests will focus on testing individual components in isolation, with dependencies mocked as needed.

### 2. Integration Tests
Integration tests will focus on testing how components work together, with minimal mocking.

### 3. End-to-End Tests
End-to-end tests will simulate user flows and test the entire system.

## Critical Components to Test

### Services Layer

#### ApplicationUploaderService
- **Unit Tests**:
  - Test `insert_application_jobs` with various input combinations
  - Test error handling and exception paths
  - Test interaction with notification service

#### PdfResumeService
- **Unit Tests**:
  - Test `store_pdf_resume` functionality
  - Test error handling and exception paths

#### NotificationPublisher / BasePublisher
- **Unit Tests**:
  - Test `publish_application_updated` functionality
  - Test queue name resolution
  - Test interaction with RabbitMQ client

#### AsyncRabbitMQClient
- **Unit Tests**:
  - Test `connect` functionality
  - Test `ensure_queue` functionality
  - Test `publish_message` functionality
  - Test `consume_messages` functionality
  - Test `close` functionality
  - Test error handling and reconnection logic

### API Layer

#### Router Endpoints
- **Integration Tests**:
  - Test `submit_jobs_and_save_application` endpoint
  - Test `get_successful_applications` endpoint
  - Test `get_successful_application_details` endpoint
  - Test `get_failed_applications` endpoint
  - Test `get_failed_application_details` endpoint
  - Test error responses and status codes

#### Helper Functions
- **Unit Tests**:
  - Test `fetch_user_doc` functionality
  - Test `parse_applications` functionality

### Core Components

#### MongoDB Integration
- **Integration Tests**:
  - Test connection and query functionality
  - Test document insertion and retrieval
  - Test error handling

#### RabbitMQ Integration
- **Integration Tests**:
  - Test message publishing
  - Test message consumption
  - Test reconnection logic
  - Test error handling

#### Authentication
- **Integration Tests**:
  - Test JWT authentication
  - Test user authorization
  - Test protected routes

## Test Implementation Plan

### 1. Setup Test Environment

#### Test Dependencies
- **pytest**: Main testing framework
- **pytest-asyncio**: For testing async functions
- **pytest-cov**: For measuring code coverage
- **unittest.mock**: For mocking dependencies
- **mongomock**: For mocking MongoDB
- **aio-pika-mock**: For mocking RabbitMQ

#### Test Configuration
- Create a test configuration file to store test-specific settings
- Set up test databases for MongoDB
- Set up test queues for RabbitMQ

### 2. Implement Test Fixtures

- **MongoDB Fixtures**:
  - Create test databases and collections
  - Initialize with test data
  - Clean up after tests

- **RabbitMQ Fixtures**:
  - Create test connections and channels
  - Set up test queues
  - Clean up after tests

- **Authentication Fixtures**:
  - Create test users and tokens
  - Set up test dependencies for authentication

### 3. Implement Test Cases

#### Unit Tests for Services

##### ApplicationUploaderService Tests
```python
# tests/services/test_application_uploader_service.py

import pytest
from unittest.mock import AsyncMock, patch
from app.services.application_uploader_service import ApplicationUploaderService
from app.core.exceptions import DatabaseOperationError

@pytest.mark.asyncio
async def test_insert_application_jobs_success():
    # Arrange
    mock_applications_collection = AsyncMock()
    mock_applications_collection.insert_one.return_value.inserted_id = "mock_id"
    mock_notification_publisher = AsyncMock()
    
    with patch('app.services.application_uploader_service.applications_collection', mock_applications_collection), \
         patch('app.services.application_uploader_service.notification_publisher', mock_notification_publisher):
        
        service = ApplicationUploaderService()
        user_id = "test_user"
        job_list = [{"title": "Software Engineer", "description": "Test job"}]
        
        # Act
        result = await service.insert_application_jobs(user_id, job_list)
        
        # Assert
        assert result == "mock_id"
        mock_applications_collection.insert_one.assert_called_once()
        mock_notification_publisher.publish_application_updated.assert_awaited_once()

@pytest.mark.asyncio
async def test_insert_application_jobs_with_cv():
    # Arrange
    mock_applications_collection = AsyncMock()
    mock_applications_collection.insert_one.return_value.inserted_id = "mock_id"
    mock_notification_publisher = AsyncMock()
    
    with patch('app.services.application_uploader_service.applications_collection', mock_applications_collection), \
         patch('app.services.application_uploader_service.notification_publisher', mock_notification_publisher):
        
        service = ApplicationUploaderService()
        user_id = "test_user"
        job_list = [{"title": "Software Engineer", "description": "Test job"}]
        cv_id = "test_cv_id"
        
        # Act
        result = await service.insert_application_jobs(user_id, job_list, cv_id=cv_id)
        
        # Assert
        assert result == "mock_id"
        mock_applications_collection.insert_one.assert_called_once()
        # Check that gen_cv was set to False
        called_args = mock_applications_collection.insert_one.call_args[0][0]
        assert called_args["jobs"][0]["gen_cv"] == False
        mock_notification_publisher.publish_application_updated.assert_awaited_once()

@pytest.mark.asyncio
async def test_insert_application_jobs_database_error():
    # Arrange
    mock_applications_collection = AsyncMock()
    mock_applications_collection.insert_one.side_effect = Exception("DB Error")
    
    with patch('app.services.application_uploader_service.applications_collection', mock_applications_collection):
        
        service = ApplicationUploaderService()
        user_id = "test_user"
        job_list = [{"title": "Software Engineer", "description": "Test job"}]
        
        # Act & Assert
        with pytest.raises(DatabaseOperationError):
            await service.insert_application_jobs(user_id, job_list)
```

##### PdfResumeService Tests
```python
# tests/services/test_pdf_resume_service.py

import pytest
from unittest.mock import AsyncMock, patch
from app.services.pdf_resume_service import PdfResumeService
from app.core.exceptions import DatabaseOperationError

@pytest.mark.asyncio
async def test_store_pdf_resume_success():
    # Arrange
    mock_pdf_resumes_collection = AsyncMock()
    mock_pdf_resumes_collection.insert_one.return_value.inserted_id = "mock_id"
    
    with patch('app.services.pdf_resume_service.pdf_resumes_collection', mock_pdf_resumes_collection):
        
        service = PdfResumeService()
        pdf_bytes = b"test pdf content"
        
        # Act
        result = await service.store_pdf_resume(pdf_bytes)
        
        # Assert
        assert result == "mock_id"
        mock_pdf_resumes_collection.insert_one.assert_called_once_with({
            "cv": pdf_bytes,
            "app_ids": []
        })

@pytest.mark.asyncio
async def test_store_pdf_resume_database_error():
    # Arrange
    mock_pdf_resumes_collection = AsyncMock()
    mock_pdf_resumes_collection.insert_one.side_effect = Exception("DB Error")
    
    with patch('app.services.pdf_resume_service.pdf_resumes_collection', mock_pdf_resumes_collection):
        
        service = PdfResumeService()
        pdf_bytes = b"test pdf content"
        
        # Act & Assert
        with pytest.raises(DatabaseOperationError):
            await service.store_pdf_resume(pdf_bytes)
```

##### NotificationPublisher Tests
```python
# tests/services/test_notification_service.py

import pytest
from unittest.mock import AsyncMock, patch
from app.services.notification_service import NotificationPublisher

@pytest.mark.asyncio
async def test_get_queue_name():
    # Arrange
    mock_settings = AsyncMock()
    mock_settings.middleware_queue = "test_queue"
    
    with patch('app.services.notification_service.settings', mock_settings):
        
        publisher = NotificationPublisher()
        
        # Act
        result = publisher.get_queue_name()
        
        # Assert
        assert result == "test_queue"

@pytest.mark.asyncio
async def test_publish_application_updated():
    # Arrange
    mock_publish = AsyncMock()
    
    publisher = NotificationPublisher()
    publisher.publish = mock_publish
    
    # Act
    await publisher.publish_application_updated()
    
    # Assert
    mock_publish.assert_awaited_once_with({"updated": True}, False)
```

##### AsyncRabbitMQClient Tests
```python
# tests/core/test_rabbitmq_client.py

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import aio_pika
from app.core.rabbitmq_client import AsyncRabbitMQClient

@pytest.mark.asyncio
async def test_connect_new_connection():
    # Arrange
    mock_connect = AsyncMock()
    mock_connection = AsyncMock()
    mock_connection.channel.return_value = AsyncMock()
    mock_connect.return_value = mock_connection
    
    with patch('app.core.rabbitmq_client.aio_pika.connect_robust', mock_connect):
        
        client = AsyncRabbitMQClient("amqp://localhost")
        
        # Act
        await client.connect()
        
        # Assert
        mock_connect.assert_called_once_with("amqp://localhost")
        assert client.connection == mock_connection
        assert client.channel == mock_connection.channel.return_value

@pytest.mark.asyncio
async def test_connect_existing_connection():
    # Arrange
    client = AsyncRabbitMQClient("amqp://localhost")
    client.connection = AsyncMock()
    client.connection.is_closed = False
    mock_connect = AsyncMock()
    
    with patch('app.core.rabbitmq_client.aio_pika.connect_robust', mock_connect):
        
        # Act
        await client.connect()
        
        # Assert
        mock_connect.assert_not_called()

@pytest.mark.asyncio
async def test_connect_failure():
    # Arrange
    mock_connect = AsyncMock()
    mock_connect.side_effect = Exception("Connection error")
    
    with patch('app.core.rabbitmq_client.aio_pika.connect_robust', mock_connect):
        
        client = AsyncRabbitMQClient("amqp://localhost")
        
        # Act & Assert
        with pytest.raises(Exception):
            await client.connect()

@pytest.mark.asyncio
async def test_ensure_queue():
    # Arrange
    mock_connect = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()
    mock_channel.declare_queue.return_value = mock_queue
    
    client = AsyncRabbitMQClient("amqp://localhost")
    client.connect = mock_connect
    client.channel = mock_channel
    
    # Act
    result = await client.ensure_queue("test_queue", durable=True)
    
    # Assert
    mock_connect.assert_called_once()
    mock_channel.declare_queue.assert_called_once_with("test_queue", durable=True)
    assert result == mock_queue

@pytest.mark.asyncio
async def test_publish_message():
    # Arrange
    mock_connect = AsyncMock()
    mock_ensure_queue = AsyncMock()
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_channel.default_exchange = mock_exchange
    
    client = AsyncRabbitMQClient("amqp://localhost")
    client.connect = mock_connect
    client.ensure_queue = mock_ensure_queue
    client.channel = mock_channel
    
    message = {"key": "value"}
    
    # Act
    await client.publish_message("test_queue", message, persistent=True)
    
    # Assert
    mock_connect.assert_called_once()
    mock_ensure_queue.assert_called_once_with("test_queue", durable=False)
    
    # Check that the message was published correctly
    mock_exchange.publish.assert_called_once()
    call_args = mock_exchange.publish.call_args
    assert call_args[1]["routing_key"] == "test_queue"
    
    # Check message content
    message_arg = call_args[0][0]
    assert message_arg.body == json.dumps(message).encode()
    assert message_arg.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

@pytest.mark.asyncio
async def test_close_connection():
    # Arrange
    mock_connection = AsyncMock()
    
    client = AsyncRabbitMQClient("amqp://localhost")
    client.connection = mock_connection
    mock_connection.is_closed = False
    
    # Act
    await client.close()
    
    # Assert
    mock_connection.close.assert_called_once()
```

#### Integration Tests for API Endpoints

```python
# tests/routers/test_app_router_integration.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import json
from app.main import app
from app.core.auth import get_current_user

TEST_USER_ID = "test_user_integration"

async def mock_get_current_user():
    return TEST_USER_ID

app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.mark.asyncio
async def test_submit_jobs_with_pdf(test_client):
    # Arrange
    test_jobs = [
        {
            "job_id": 12345,
            "description": "Test job description",
            "portal": "LinkedIn",
            "title": "Software Engineer"
        }
    ]
    
    # Mock PDF resume service
    mock_pdf_service = AsyncMock()
    mock_pdf_service.store_pdf_resume.return_value = "pdf_id_123"
    
    # Mock application uploader service
    mock_app_uploader = AsyncMock()
    mock_app_uploader.insert_application_jobs.return_value = "app_id_123"
    
    with patch('app.routers.app_router.pdf_resume_service', mock_pdf_service), \
         patch('app.routers.app_router.application_uploader', mock_app_uploader):
        
        # Act
        jobs_payload = json.dumps({"jobs": test_jobs})
        pdf_content = b"fake PDF content"
        
        response = test_client.post(
            "/applications",
            data={"jobs": jobs_payload, "style": "professional"},
            files={"cv": ("resume.pdf", pdf_content, "application/pdf")}
        )
        
        # Assert
        assert response.status_code == 200
        assert response.json() is True
        
        # Check that services were called with correct parameters
        mock_pdf_service.store_pdf_resume.assert_awaited_once_with(pdf_content)
        mock_app_uploader.insert_application_jobs.assert_awaited_once()
        
        # Check the parameters passed to insert_application_jobs
        call_args = mock_app_uploader.insert_application_jobs.call_args
        assert call_args.kwargs["user_id"] == TEST_USER_ID
        assert call_args.kwargs["cv_id"] == "pdf_id_123"
        assert call_args.kwargs["style"] == "professional"
        assert len(call_args.kwargs["job_list_to_apply"]) == 1
        assert call_args.kwargs["job_list_to_apply"][0]["job_id"] == 12345

@pytest.mark.asyncio
async def test_get_successful_applications_integration(test_client):
    # Arrange
    mock_doc = {
        "user_id": TEST_USER_ID,
        "content": {
            "app1": {
                "title": "Senior Software Engineer",
                "description": "Integration test job",
                "portal": "Indeed"
            }
        }
    }
    
    mock_mongo = AsyncMock()
    mock_db = AsyncMock()
    mock_collection = AsyncMock()
    mock_collection.find_one.return_value = mock_doc
    mock_db.get_collection.return_value = mock_collection
    mock_mongo.get_database.return_value = mock_db
    
    with patch('app.routers.app_router.mongo_client', mock_mongo):
        
        # Act
        response = test_client.get("/applied")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "app1" in data
        assert data["app1"]["title"] == "Senior Software Engineer"
        assert data["app1"]["description"] == "Integration test job"
        assert data["app1"]["portal"] == "Indeed"
        
        # Check that MongoDB was queried correctly
        mock_mongo.get_database.assert_called_once_with("resumes")
        mock_db.get_collection.assert_called_once_with("success_app")
        mock_collection.find_one.assert_called_once_with({"user_id": TEST_USER_ID})
```

### 4. Implement Test Coverage Measurement

- Configure pytest to measure code coverage:

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto

[coverage:run]
source = app
omit = 
    app/tests/*
    app/scripts/*
```

- Run tests with coverage:

```bash
pytest --cov=app --cov-report=term-missing --cov-report=html
```

## Test Execution Plan

1. **Unit Tests**: Run individual tests for each component
2. **Integration Tests**: Run tests for component interactions
3. **Coverage Analysis**: Analyze coverage results and identify areas needing additional tests
4. **Iteration**: Add more tests to improve coverage until reaching 70%+ for critical components

## Success Criteria

1. All tests pass successfully
2. Code coverage of at least 70% for critical components
3. Edge cases and error scenarios are adequately tested
4. Tests are maintainable and follow good practices