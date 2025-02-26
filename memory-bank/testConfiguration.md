# Test Configuration Implementation Plan

## 1. Update pytest.ini

Update the existing pytest.ini file with the following configuration to properly support our test suite:

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function

[coverage:run]
source = app
omit = 
    app/tests/*
    app/scripts/*
```

## 2. Add Missing Test Dependencies

Add the following dependencies to your project (they are already in your Poetry configuration, but you might need to install them):

```bash
poetry add pytest-cov mongomock --group test
```

## 3. Create Directory Structure for Tests

Create the following test directory structure:

```
tests/
├── conftest.py            # Shared fixtures
├── services/
│   ├── test_application_uploader_service.py
│   ├── test_pdf_resume_service.py
│   └── test_notification_service.py
├── core/
│   └── test_rabbitmq_client.py
└── routers/
    └── test_app_router_integration.py
```

## 4. Create Initial conftest.py

Create a conftest.py file with the following shared fixtures:

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.main import app
from app.core.auth import get_current_user

TEST_USER_ID = "test_user_123"

async def mock_get_current_user():
    return TEST_USER_ID

@pytest.fixture
def test_client():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    return TestClient(app)

@pytest.fixture
def mock_mongo_client():
    with patch('app.core.mongo.AsyncIOMotorClient') as mock:
        mock_client = AsyncMock(spec=AsyncIOMotorClient)
        mock_db = AsyncMock(spec=AsyncIOMotorDatabase)
        mock_collection = AsyncMock(spec=AsyncIOMotorCollection)
        
        mock_client.get_database.return_value = mock_db
        mock_db.get_collection.return_value = mock_collection
        
        mock.return_value = mock_client
        yield mock_client
        
@pytest.fixture
def mock_rabbitmq_client():
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
```

## 5. Running Tests with Coverage

To run the tests with coverage, use the following command:

```bash
python -m pytest --cov=app --cov-report=term-missing --cov-report=html tests/
```

This will:
1. Run all tests in the tests/ directory
2. Report coverage for the app package
3. Show missing lines in the terminal
4. Generate an HTML coverage report

## 6. Coverage Report Interpretation

After running the tests with coverage, look for:

1. **Overall coverage percentage**: Aim for at least 70% for critical components
2. **Missing lines**: Highlighted in the term-missing report
3. **HTML report**: Open htmlcov/index.html to see a detailed coverage breakdown

## 7. Iterative Improvement

Based on the coverage report:

1. Identify modules with less than 70% coverage
2. Add targeted tests for those modules
3. Focus on critical paths first:
   - Application submission flow
   - Resume storage
   - Message publishing
   - Authentication

## 8. Mock External Dependencies

When testing, ensure that you properly mock:

1. MongoDB connections and operations
2. RabbitMQ connections and operations
3. External API calls
4. File system operations

This will make your tests faster, more reliable, and focused on the application logic.