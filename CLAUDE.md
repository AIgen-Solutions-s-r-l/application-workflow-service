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

### Application Retrieval (with Pagination and Filtering)
```bash
# Paginated list of successful applications with optional filters
GET /applied?limit=20&cursor=<base64_cursor>&portal=LinkedIn&company_name=Google&title=Engineer&date_from=2025-01-01&date_to=2025-12-31

# Available filters:
# - portal: Filter by job portal (exact match, case-insensitive)
# - company_name: Filter by company name (partial match)
# - title: Filter by job title (partial match)
# - date_from: Filter applications from this date (ISO 8601)
# - date_to: Filter applications until this date (ISO 8601)

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

# Failed applications (same pagination and filters)
GET /fail_applied?limit=20&cursor=<base64_cursor>&portal=LinkedIn
GET /fail_applied/{app_id}
```

All endpoints require `Authorization: Bearer <jwt_token>` header.

### Prometheus Metrics
```bash
GET /metrics
# Returns Prometheus-formatted metrics for monitoring
```

Key metrics available:
- `http_request_duration_seconds`: Request latency histogram
- `http_requests_total`: Total request counter by endpoint/status
- `applications_submitted_total`: Application submission counter
- `queue_messages_published_total`: Queue publish counter
- `dlq_messages_total`: Dead letter queue counter
- `rate_limit_exceeded_total`: Rate limit violations counter

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
├── test_sprint1_features.py # Sprint 1 feature tests (status, pagination, notifications)
├── test_sprint2_features.py # Sprint 2 feature tests (async, rate limit, retry)
├── test_sprint3_features.py # Sprint 3 feature tests (metrics, correlation, filtering)
└── test_sprint4_features.py # Sprint 4 feature tests (health, errors, idempotency)
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

### Correlation IDs

All requests are traced with correlation IDs:
- Incoming `X-Correlation-ID` header is used if present
- New UUID is generated if no header provided
- ID is included in response headers (`X-Correlation-ID`, `X-Request-ID`)
- ID propagates to queue messages and log entries

Use correlation IDs to trace requests across services:
```bash
curl -H "X-Correlation-ID: my-trace-123" /applications
# Response includes: X-Correlation-ID: my-trace-123
```

### Idempotency Keys

Prevent duplicate submissions using idempotency keys:
```bash
curl -X POST /applications \
  -H "X-Idempotency-Key: unique-request-id-123" \
  -H "Authorization: Bearer <token>" \
  ...
```

- Keys are stored for 24 hours
- Duplicate requests return cached response with `X-Idempotency-Replayed: true`
- Failed requests allow retry with same key

### Structured Error Responses

All errors return structured JSON:
```json
{
  "error": "ApplicationNotFoundError",
  "code": "ERR_2001",
  "message": "Application not found: app_123",
  "correlation_id": "abc-123",
  "timestamp": "2025-02-27T10:00:00Z",
  "details": null
}
```

Error code ranges:
- `ERR_1xxx`: General errors (validation, not found)
- `ERR_2xxx`: Application errors
- `ERR_3xxx`: Job errors
- `ERR_4xxx`: Resume errors
- `ERR_5xxx`: Database errors
- `ERR_6xxx`: Queue errors
- `ERR_7xxx`: Rate limit errors
- `ERR_8xxx`: Authentication errors
- `ERR_9xxx`: Idempotency errors

### Health Check Endpoints

Kubernetes-compatible health probes:
```bash
# Liveness probe (is the service running?)
GET /health/live
# Returns: {"status": "alive", "timestamp": "..."}

# Readiness probe (can handle traffic?)
GET /health/ready
# Returns: {"status": "ready", "checks": {"mongodb": "ready", "rabbitmq": "ready"}}

# Full health check with details
GET /health
# Returns: {"status": "healthy", "dependencies": [...], "environment": "..."}
```

### SLO Configuration

Service Level Objectives are defined in `monitoring/slo-config.yaml`:
- **Availability**: 99.9% (non-5xx responses)
- **Latency P95**: 95% under 500ms
- **Latency P99**: 99% under 2s
- **Processing Success**: 99% applications processed successfully

Alerting rules included for:
- High error rate
- High latency (P95/P99)
- Service down
- Database/queue issues
- Error budget burn rate

## Performance Optimization

### Database Configuration (`app/core/database.py`)

The service uses optimized MongoDB connections with:
- **Connection Pooling**: Configurable pool size (default: 10-100 connections)
- **Automatic Index Creation**: Indexes created on startup for query optimization
- **Compression**: zstd, snappy, zlib compression support

Key indexes:
- `jobs_to_apply_per_user`: user_id, status, created_at (compound indexes)
- `success_app`/`failed_app`: user_id, portal
- `idempotency_keys`: key (unique), TTL index for auto-expiration

Configuration options:
```env
MONGO_MAX_POOL_SIZE=100
MONGO_MIN_POOL_SIZE=10
MONGO_MAX_IDLE_TIME_MS=30000
MONGO_CONNECT_TIMEOUT_MS=5000
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
MONGO_SOCKET_TIMEOUT_MS=30000
```

### Caching (`app/core/cache.py`)

In-memory LRU cache with TTL support:
- `application_cache`: 1000 entries, 60s TTL
- `user_cache`: 500 entries, 300s TTL

Usage:
```python
from app.core.cache import async_cached, application_cache

@async_cached(application_cache, ttl=60, key_prefix="app_status")
async def get_status(app_id: str) -> dict:
    ...
```

## Security Features

### Security Headers (`app/core/security_headers.py`)

Middleware adds OWASP-recommended security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` (disables camera, microphone, etc.)
- `Strict-Transport-Security` (production only)

### Audit Logging (`app/core/audit.py`)

Structured audit logging for security events:

```python
from app.core.audit import audit_logger

# Authentication events
audit_logger.log_auth_success(user_id="123", ip_address="192.168.1.1")
audit_logger.log_auth_failure(user_id="123", reason="Invalid credentials")

# Application events
audit_logger.log_application_created(user_id="123", application_id="456", job_count=5)
audit_logger.log_application_status_changed(user_id="123", application_id="456", old_status="pending", new_status="processing")

# Security events
audit_logger.log_rate_limit_exceeded(user_id="123", endpoint="/applications")
audit_logger.log_suspicious_activity(description="Multiple failed auth attempts")
```

Event types: `auth.*`, `authz.*`, `application.*`, `resume.*`, `security.*`

### Input Validation (`app/core/input_validation.py`)

Comprehensive input validation and sanitization:

```python
from app.core.input_validation import (
    validate_and_sanitize,
    detect_injection,
    validate_file_upload,
    sanitize_mongodb_query
)

# Sanitize user input
clean_input = validate_and_sanitize(user_input, "field_name", max_length=1000)

# Detect potential attacks
injection_type = detect_injection(value)  # Returns: "sql_injection", "xss", "nosql_injection", etc.

# Validate file uploads
validate_file_upload(file, allowed_types=["application/pdf"], max_size_mb=10)

# Sanitize MongoDB queries
safe_query = sanitize_mongodb_query(user_provided_query)
```

Protected against:
- SQL/NoSQL injection
- XSS (Cross-Site Scripting)
- Path traversal attacks
- Dangerous file uploads

## New Features

### WebSocket Real-Time Updates (`app/core/websocket_manager.py`)

Real-time status updates via WebSocket:

```javascript
// Connect with JWT token
const ws = new WebSocket('ws://localhost:8009/ws/status?token=<jwt_token>');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // data.type: "connected", "status_update", "batch_update", "ping"
    console.log(data);
};

// Keepalive
ws.send("ping");  // Receives "pong"
```

Message types:
- `connected`: Initial connection confirmation
- `status_update`: Application status changed
- `batch_update`: Batch processing progress
- `ping`: Keepalive response

### Batch Operations (`app/routers/batch_router.py`)

Submit multiple applications at once:

```bash
POST /batch/applications
Content-Type: multipart/form-data

# items: JSON array of {jobs: [...], style: "..."}
curl -X POST "http://localhost:8009/batch/applications" \
  -H "Authorization: Bearer <token>" \
  -F 'items=[{"jobs":[...],"style":"modern"},{"jobs":[...],"style":"classic"}]' \
  -F 'cv=@shared_resume.pdf'

# Response: {"batch_id": "...", "status": "pending", "total": 2}

# Check batch status
GET /batch/applications/{batch_id}

# Cancel batch
DELETE /batch/applications/{batch_id}
```

### Data Export (`app/routers/export_router.py`)

Export applications to CSV or Excel:

```bash
# Get export summary
GET /export/summary

# Download CSV
GET /export/csv?include_successful=true&include_failed=true&portal=LinkedIn

# Download Excel (with formatting)
GET /export/excel?date_from=2025-01-01&date_to=2025-12-31

# Stream large exports
GET /export/csv?stream=true
```

## Observability

### OpenTelemetry Tracing (`app/core/tracing.py`)

Distributed tracing with OpenTelemetry:

```env
TRACING_ENABLED=true
TRACING_EXPORTER=jaeger  # console, jaeger, otlp
JAEGER_HOST=localhost
JAEGER_PORT=6831
OTLP_ENDPOINT=http://localhost:4317
TRACING_SAMPLE_RATE=1.0
```

Usage in code:
```python
from app.core.tracing import traced, create_span, add_span_attributes

@traced(name="process_application")
async def process_application(app_id: str):
    add_span_attributes({"application_id": app_id})
    ...

# Or manually
with create_span("custom_operation", {"key": "value"}):
    ...
```

### Prometheus Alerting (`monitoring/prometheus-alerts.yaml`)

Pre-configured alerts for:
- Service availability (ServiceDown, HighErrorRate)
- Latency (HighLatencyP95, HighLatencyP99)
- Application processing (HighApplicationFailureRate, ProcessingBacklog)
- Queue health (HighDLQMessages, QueuePublishFailures)
- Rate limiting (HighRateLimitViolations)
- Resources (HighMemoryUsage, HighCPUUsage)
- SLO burn rate (multi-window alerts)

### Log Aggregation (`monitoring/loki-config.yaml`)

Loki/Promtail configuration for centralized logging:
- JSON log parsing
- Label extraction (level, event_type, correlation_id)
- Pre-built LogQL queries for dashboards
- Alerting rules for log patterns

## Development Notes

- **Application Status**: Applications now have full lifecycle tracking with status and timestamps
- **Pagination**: List endpoints support cursor-based pagination with configurable limits
- **Notification Payloads**: Enriched event payloads replace the simple `{"updated": true}` format
- **Database Config**: Database name is now configurable via `MONGODB_DATABASE` env var
- **JobData ID Format**: The `id` field was changed from UUID to string (Feb 2025)
- **Resume Upload**: CV/resume upload is optional in application submission
- **Authentication**: JWT token must contain `id` field (user ID as string)
- **Logging**: Service uses loguru with configurable JSON output for production
- **Database Initialization**: Indexes are created automatically on startup via lifespan handler
- **Security Headers**: Added in production mode; HSTS disabled in development
- **WebSocket**: Real-time updates available at `/ws/status`
- **Batch Processing**: Up to 100 applications per batch
- **Export**: CSV streaming for large datasets, Excel with color-coded formatting
