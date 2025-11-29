# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Application Manager Service is a Python FastAPI backend that manages job application workflows. The service handles resume processing, job application tracking, and categorizes applications as successful or failed. It uses MongoDB for data persistence and RabbitMQ for asynchronous notifications.

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: MongoDB (with Motor async driver)
- **Message Broker**: RabbitMQ (aio-pika)
- **Authentication**: JWT-based (python-jose)
- **Testing**: pytest with pytest-asyncio
- **Dependency Management**: Poetry

## Development Commands

### Setup
```bash
# Install dependencies
poetry install

# Or using pip
pip install -r requirements.txt

# Activate virtual environment (if using venv)
source .venv/bin/activate
```

### Running the Application
```bash
# Standard run
python app/main.py

# With uvicorn directly (recommended for development)
uvicorn app.main:app --reload --port 8009
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage report
./run_tests_with_coverage.sh
# OR
python -m pytest --cov=app --cov-report=term-missing --cov-report=html tests/

# Run specific test file
pytest tests/services/test_application_uploader_service.py

# Run tests matching a pattern
pytest -k "application_uploader"

# Run tests in specific directory
pytest tests/services/
```

### Docker
```bash
# Build image
docker build -t application-manager-service .

# Run container
docker run -p 8009:8000 application-manager-service
```

## Architecture

### Directory Structure
```
app/
├── core/           # Core functionality (config, auth, DB clients)
├── models/         # Pydantic models (JobData, etc.)
├── routers/        # FastAPI route handlers
├── schemas/        # Request/response schemas
├── services/       # Business logic layer
└── scripts/        # Database initialization scripts
```

### Key Services

**ApplicationUploaderService** (`app/services/application_uploader_service.py`)
- Stores job application data in MongoDB
- Handles application state management (pending/success/failed)

**PdfResumeService** (`app/services/pdf_resume_service.py`)
- Manages PDF resume storage and retrieval
- Stores resumes in MongoDB with user_id association

**NotificationService** (`app/services/notification_service.py`)
- Publishes application status notifications to RabbitMQ
- Uses the `middleware_notification_queue` queue

### MongoDB Collections

- `applications_collection`: Pending job applications
- `pdf_resumes_collection`: User-uploaded PDF resumes
- `success_app`: Successfully processed applications
- `failed_app`: Failed applications

### Authentication Flow

JWT tokens are required for all `/applications` and `/applied` endpoints. The token payload must contain a user `id` field. Authentication is handled in `app/core/auth.py` using the `get_current_user` dependency.

### Data Models

**JobData** (`app/models/job.py`)
- Primary model for job information
- `id` field is `Optional[str]` (changed from UUID for flexibility)
- Contains portal, title, company, location, description, etc.

**Important**: The `id` field in JobData is a string, not a UUID. This allows compatibility with various external ID formats.

## Configuration

Environment variables are managed through `app/core/config.py`. Create a `.env` file with:

```env
SERVICE_NAME=application_manager_service
MONGODB=mongodb://localhost:27017
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
MIDDLEWARE_QUEUE=middleware_notification_queue
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
DEBUG=True
ENVIRONMENT=development
```

## API Endpoints

### Application Submission
```bash
POST /applications
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

# CV is OPTIONAL - can be omitted entirely if user doesn't upload
-F 'jobs={"jobs":[{...}]}'
-F 'style=samudum_bold'
-F 'cv=@/path/to/file.pdf'  # Optional
```

### Application Retrieval
```bash
GET /applied                # All successful applications (excludes resume_optimized, cover_letter)
GET /applied/{app_id}       # Detailed info for specific success (only resume_optimized, cover_letter)
GET /fail_applied           # All failed applications
GET /fail_applied/{app_id}  # Detailed info for specific failure
```

All endpoints require `Authorization: Bearer <jwt_token>` header.

## Testing Guidelines

### Coverage Target
Aim for 70% minimum coverage on critical components:
- Service layer (ApplicationUploaderService, PdfResumeService, NotificationService)
- Core components (AsyncRabbitMQClient, auth)
- API endpoints

### Test Organization
```
tests/
├── conftest.py              # Shared fixtures and mocks
├── services/                # Service layer tests
├── core/                    # Core component tests
├── routers/                 # API endpoint tests
└── integration/             # End-to-end workflow tests
```

### Async Testing
All async functions use `pytest-asyncio` with `asyncio_mode = auto` configured in `pytest.ini`. Tests for async code should be marked with `async def test_*`.

### Mocking External Dependencies
- MongoDB operations are mocked using `pytest-mock` or `unittest.mock`
- RabbitMQ connections use mocked `AsyncRabbitMQClient`
- JWT authentication can be bypassed in tests by overriding dependencies

## Future Architecture Notes

The memory-bank documents describe a planned migration to worker-based asynchronous processing:
- API tier will return immediately with tracking IDs
- Workers will consume from RabbitMQ and process applications asynchronously
- Status endpoints will allow clients to poll application progress

When implementing new features, consider compatibility with this future architecture. Keep business logic in services rather than routers to facilitate eventual extraction to workers.

## Development Notes

- **JobData ID Format**: The `id` field was changed from UUID to string (Feb 2025) for flexibility with external systems
- **Resume Upload**: CV/resume upload is optional in application submission
- **Authentication**: JWT token must contain `id` field (user ID as string)
- **Logging**: Service uses loguru with configurable JSON output for production
- **Poetry vs pip**: Project uses Poetry for dependency management, but requirements.txt is available for pip-based workflows
