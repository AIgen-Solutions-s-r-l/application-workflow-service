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
├── core/           # Core functionality (config, auth, DB clients, rate limiting, retry)
├── models/         # Pydantic models (JobData, Application, etc.)
├── routers/        # FastAPI route handlers
├── schemas/        # Request/response schemas
├── services/       # Business logic layer
├── workers/        # Async workers for background processing
└── scripts/        # Database initialization scripts
```

### Key Services

**ApplicationUploaderService** (`app/services/application_uploader_service.py`)
- Stores job application data in MongoDB with status tracking
- Handles application state management (pending → processing → success/failed)
- Provides status querying and updates with timestamps

**PdfResumeService** (`app/services/pdf_resume_service.py`)
- Manages PDF resume storage and retrieval
- Stores resumes in MongoDB with user_id association

**NotificationService** (`app/services/notification_service.py`)
- Publishes enriched application status notifications to RabbitMQ
- Event types: `application.submitted`, `application.status_changed`
- Uses the `middleware_notification_queue` queue

**QueueService** (`app/services/queue_service.py`)
- Publishes applications to the processing queue for async processing
- Handles dead letter queue (DLQ) publishing for failed messages
- Configurable via `ASYNC_PROCESSING_ENABLED` setting

**ApplicationWorker** (`app/workers/application_worker.py`)
- Consumes from `application_processing_queue`
- Processes applications with retry and exponential backoff
- Moves failed applications to DLQ after max retries
- Run as standalone: `python -m app.workers.application_worker`

### MongoDB Collections

- `jobs_to_apply_per_user`: Pending job applications (via `applications_collection`)
- `pdf_resumes`: User-uploaded PDF resumes
- `success_app`: Successfully processed applications
- `failed_app`: Failed applications

### Application Status Lifecycle

Applications follow this status progression:

```
pending → processing → success
                    ↘ failed
```

Each application document includes:
- `status`: Current state (pending/processing/success/failed)
- `created_at`: When the application was submitted
- `updated_at`: When the application was last modified
- `processed_at`: When the application reached a terminal state
- `error_reason`: Error message if failed

### Authentication Flow

JWT tokens are required for all `/applications` and `/applied` endpoints. The token payload must contain a user `id` field. Authentication is handled in `app/core/auth.py` using the `get_current_user` dependency.

### Data Models

**Application** (`app/models/application.py`)
- Primary model for application documents with status tracking
- `ApplicationStatus` enum: PENDING, PROCESSING, SUCCESS, FAILED
- Includes timestamps: created_at, updated_at, processed_at

**JobData** (`app/models/job.py`)
- Model for job information within applications
- `id` field is `Optional[str]` (changed from UUID for flexibility)
- Contains portal, title, company, location, description, etc.

## Configuration

Environment variables are managed through `app/core/config.py`. Create a `.env` file with:

```env
SERVICE_NAME=application_manager_service
MONGODB=mongodb://localhost:27017
MONGODB_DATABASE=resumes
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
MIDDLEWARE_QUEUE=middleware_notification_queue
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
DEBUG=True
ENVIRONMENT=development

# Async Processing
ASYNC_PROCESSING_ENABLED=True
APPLICATION_PROCESSING_QUEUE=application_processing_queue
APPLICATION_DLQ=application_dlq

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_APPLICATIONS=100/hour
RATE_LIMIT_REQUESTS=1000/hour

# Retry Configuration
MAX_RETRIES=5
RETRY_BASE_DELAY=1.0
RETRY_MAX_DELAY=16.0
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

# Response (new format with tracking):
{
    "application_id": "abc123",
    "status": "pending",
    "status_url": "/applications/abc123/status",
    "job_count": 5,
    "created_at": "2025-02-27T10:00:00Z"
}
```

### Application Status
```bash
GET /applications/{application_id}/status
Authorization: Bearer <jwt_token>

# Response:
{
    "application_id": "abc123",
    "status": "processing",
    "created_at": "2025-02-27T10:00:00Z",
    "updated_at": "2025-02-27T10:05:00Z",
    "processed_at": null,
    "job_count": 5,
    "error_reason": null
}
```

### Application Retrieval (with Pagination)
```bash
# Paginated list of successful applications
GET /applied?limit=20&cursor=<base64_cursor>

# Response:
{
    "data": {"app_id_1": {...}, "app_id_2": {...}},
    "pagination": {
        "limit": 20,
        "next_cursor": "eyJpZCI6IjEyMyJ9",
        "has_more": true,
        "total_count": 150
    }
}

# Detailed info for specific application
GET /applied/{app_id}

# Failed applications (same pagination)
GET /fail_applied?limit=20&cursor=<base64_cursor>
GET /fail_applied/{app_id}
```

All endpoints require `Authorization: Bearer <jwt_token>` header.

### Notification Payload Format

Notifications are published to RabbitMQ with enriched payloads:

```json
{
    "event": "application.submitted",
    "version": "1.0",
    "application_id": "abc123",
    "user_id": "user456",
    "status": "pending",
    "job_count": 5,
    "timestamp": "2025-02-27T10:00:00Z"
}
```

For status changes, additional fields are included:
- `previous_status`: The status before the change
- `error_reason`: Error message if status is "failed"

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
├── integration/             # End-to-end workflow tests
├── test_sprint1_features.py # Sprint 1 feature tests
└── test_sprint2_features.py # Sprint 2 feature tests (async, rate limit, retry)
```

### Async Testing
All async functions use `pytest-asyncio` with `asyncio_mode = auto` configured in `pytest.ini`. Tests for async code should be marked with `async def test_*`.

### Mocking External Dependencies
- MongoDB operations are mocked using `pytest-mock` or `unittest.mock`
- RabbitMQ connections use mocked `AsyncRabbitMQClient`
- JWT authentication can be bypassed in tests by overriding dependencies

## Async Processing Architecture

The service now supports asynchronous application processing:

1. **Submission**: POST /applications returns immediately with tracking ID
2. **Queue**: Application is published to `application_processing_queue`
3. **Worker**: ApplicationWorker consumes and processes applications
4. **Status**: Clients poll GET /applications/{id}/status for progress

### Running the Worker

```bash
# As a module
python -m app.workers.application_worker

# Or directly
python app/workers/application_worker.py
```

### Rate Limiting

The service includes per-user rate limiting:
- Global middleware applies to all endpoints (configurable via `RATE_LIMIT_REQUESTS`)
- Health check endpoints are excluded from rate limiting
- Rate limit headers are included in all responses:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Remaining requests in window
  - `X-RateLimit-Reset`: Unix timestamp when window resets

### Retry Mechanism

Failed operations are retried with exponential backoff:
- Base delay starts at `RETRY_BASE_DELAY` seconds
- Delay doubles each attempt up to `RETRY_MAX_DELAY`
- After `MAX_RETRIES` attempts, message goes to DLQ

Error classification:
- **Retryable**: Network timeouts, connection errors, rate limits, 5xx errors
- **Non-retryable**: Invalid data, authentication failures, business logic errors

## Development Notes

- **Application Status**: Applications now have full lifecycle tracking with status and timestamps
- **Pagination**: List endpoints support cursor-based pagination with configurable limits
- **Notification Payloads**: Enriched event payloads replace the simple `{"updated": true}` format
- **Database Config**: Database name is now configurable via `MONGODB_DATABASE` env var
- **JobData ID Format**: The `id` field was changed from UUID to string (Feb 2025)
- **Resume Upload**: CV/resume upload is optional in application submission
- **Authentication**: JWT token must contain `id` field (user ID as string)
- **Logging**: Service uses loguru with configurable JSON output for production
