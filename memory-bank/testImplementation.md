# Test Suite Implementation Plan

This document provides a step-by-step guide for implementing the comprehensive test suite for the Application Manager Service, with the goal of achieving at least 70% code coverage for critical components.

## Implementation Strategy

We'll implement the test suite incrementally, starting with the most critical components and gradually expanding coverage. The implementation will follow these phases:

1. **Core Service Tests**: Test the fundamental service classes first
2. **API Endpoint Tests**: Test the API endpoints that users interact with
3. **Integration Tests**: Test how components work together
4. **Edge Case & Error Handling Tests**: Ensure the system properly handles failures

## Test Files to Create

### Phase 1: Core Service Tests

#### 1. ApplicationUploaderService Tests

Create file: `tests/services/test_application_uploader_service.py`

```python
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
    # Test handling CV ID and setting gen_cv to False
    # ...

@pytest.mark.asyncio
async def test_insert_application_jobs_with_style():
    # Test handling style parameter
    # ...

@pytest.mark.asyncio
async def test_insert_application_jobs_database_error():
    # Test error handling
    # ...
```

#### 2. PdfResumeService Tests

Create file: `tests/services/test_pdf_resume_service.py`

```python
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
    # Test error handling
    # ...
```

#### 3. NotificationPublisher Tests

Create file: `tests/services/test_notification_service.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.notification_service import NotificationPublisher

@pytest.mark.asyncio
async def test_get_queue_name():
    # Test queue name resolution
    # ...

@pytest.mark.asyncio
async def test_publish_application_updated():
    # Test notification publishing
    # ...
```

#### 4. AsyncRabbitMQClient Tests

Create file: `tests/core/test_rabbitmq_client.py`

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import aio_pika
from app.core.rabbitmq_client import AsyncRabbitMQClient

@pytest.mark.asyncio
async def test_connect_new_connection():
    # Test new connection creation
    # ...

@pytest.mark.asyncio
async def test_connect_existing_connection():
    # Test reusing existing connection
    # ...

@pytest.mark.asyncio
async def test_connect_failure():
    # Test connection failure handling
    # ...

@pytest.mark.asyncio
async def test_ensure_queue():
    # Test queue declaration
    # ...

@pytest.mark.asyncio
async def test_publish_message():
    # Test message publishing
    # ...

@pytest.mark.asyncio
async def test_consume_messages():
    # Test message consumption
    # ...

@pytest.mark.asyncio
async def test_close_connection():
    # Test connection closing
    # ...
```

### Phase 2: API Endpoint Tests

#### 1. Router Helper Functions Tests

Create file: `tests/routers/test_app_router_helpers.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
import json
from fastapi import HTTPException
from app.routers.app_router import fetch_user_doc, parse_applications

@pytest.mark.asyncio
async def test_fetch_user_doc_success():
    # Test successful document fetching
    # ...

@pytest.mark.asyncio
async def test_fetch_user_doc_not_found():
    # Test handling when document is not found
    # ...

def test_parse_applications_success():
    # Test successful parsing of application data
    # ...

def test_parse_applications_with_exclude_fields():
    # Test parsing with excluded fields
    # ...

def test_parse_applications_empty():
    # Test handling empty content
    # ...

def test_parse_applications_validation_error():
    # Test handling validation errors
    # ...
```

#### 2. Application Submission Endpoint Tests

Create file: `tests/routers/test_app_router_submit.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import json
from app.main import app
from app.core.auth import get_current_user

# Tests for /applications endpoint
# ...
```

#### 3. Application Retrieval Endpoint Tests

Create file: `tests/routers/test_app_router_retrieve.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import json
from app.main import app
from app.core.auth import get_current_user

# Tests for /applied and /fail_applied endpoints
# ...
```

### Phase 3: Integration Tests

#### 1. End-to-End Application Submission Tests

Create file: `tests/integration/test_application_submission.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import json
from app.main import app

# Full flow test: submit application with resume
# ...
```

#### 2. End-to-End Application Retrieval Tests

Create file: `tests/integration/test_application_retrieval.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import json
from app.main import app

# Full flow test: retrieve application details
# ...
```

## Implementation Phases

1. **Basic Coverage (40%)**
   - Implement tests for core service classes
   - Focus on happy paths and basic functionality

2. **Medium Coverage (55%)**
   - Add API endpoint tests
   - Test helper functions
   - Add error handling tests

3. **Target Coverage (70%+)**
   - Add integration tests
   - Cover edge cases
   - Test complex scenarios

## Implementation Guidelines

1. **Test Organization**
   - Group related tests in the same file
   - Use clear, descriptive test names
   - Comment tests with Arrange/Act/Assert sections

2. **Mocking Strategy**
   - Mock external dependencies (MongoDB, RabbitMQ)
   - Use appropriate mocking techniques (patch, side_effect)
   - Ensure mocks behave like real components

3. **Test Data**
   - Use realistic test data
   - Create fixtures for common test data
   - Avoid hardcoding test data within tests

4. **Coverage Monitoring**
   - Run coverage analysis regularly
   - Identify and prioritize uncovered code
   - Focus on critical paths first

## Example Implementation Timeline

### Week 1: Core Service Tests
- Day 1-2: Set up testing infrastructure
- Day 3-4: Implement ApplicationUploaderService and PdfResumeService tests
- Day 5: Implement NotificationPublisher and AsyncRabbitMQClient tests

### Week 2: API Endpoint Tests
- Day 1-2: Implement tests for helper functions
- Day 3-4: Implement tests for application submission endpoint
- Day 5: Implement tests for application retrieval endpoints

### Week 3: Integration and Coverage Improvement
- Day 1-2: Implement integration tests
- Day 3-4: Analyze coverage and implement additional tests
- Day 5: Final coverage improvements and documentation

## Monitoring Progress

Track progress using the following metrics:

1. **Code Coverage**: Measure overall and per-module coverage
2. **Test Count**: Track the number of tests implemented
3. **Critical Path Coverage**: Ensure critical business logic has high coverage

Use continuous integration to automatically run tests and measure coverage on each commit.