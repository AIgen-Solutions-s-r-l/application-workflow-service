# Application Manager Service

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.4-009688.svg)](https://fastapi.tiangolo.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-Motor-47A248.svg)](https://motor.readthedocs.io/)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-aio--pika-FF6600.svg)](https://aio-pika.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-ready Python microservice for managing job application workflows. Built with FastAPI, it provides async processing, comprehensive observability, and enterprise-grade reliability features.

## Features

- **Async Application Processing** - Non-blocking job submission with background workers
- **Status Tracking** - Real-time application lifecycle monitoring (pending → processing → success/failed)
- **Cursor-based Pagination** - Efficient retrieval of large application lists
- **Advanced Filtering** - Filter by portal, company, title, and date range
- **Rate Limiting** - Per-user request throttling with configurable limits
- **Retry Mechanism** - Exponential backoff for transient failures
- **Idempotency Keys** - Prevent duplicate submissions
- **Prometheus Metrics** - Built-in observability with custom metrics
- **Correlation IDs** - Distributed tracing across services
- **Kubernetes-ready** - Liveness and readiness probes included
- **Structured Error Handling** - Consistent error responses with error codes

## Architecture

```mermaid
flowchart LR
    subgraph Client
        A[HTTP Client]
    end

    subgraph API["FastAPI Application"]
        B[REST API]
        C[Middlewares]
    end

    subgraph Queue["Message Broker"]
        D[(RabbitMQ)]
        E[Processing Queue]
        F[DLQ]
    end

    subgraph Worker["Background Processing"]
        G[Application Worker]
    end

    subgraph Storage["Data Layer"]
        H[(MongoDB)]
    end

    A -->|Request| B
    B --> C
    C -->|Publish| D
    D --> E
    E -->|Consume| G
    G -->|Failed| F
    B -->|Read/Write| H
    G -->|Update Status| H
```

### Application Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: Submit Application
    Pending --> Processing: Worker picks up
    Processing --> Success: Completed
    Processing --> Failed: Error
    Success --> [*]
    Failed --> [*]

    note right of Pending
        Application queued
        for processing
    end note

    note right of Processing
        Worker actively
        processing jobs
    end note
```

### Request Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI
    participant RMQ as RabbitMQ
    participant W as Worker
    participant DB as MongoDB

    C->>API: POST /applications
    API->>DB: Create application (pending)
    API->>RMQ: Publish to queue
    API-->>C: 200 OK (application_id)

    RMQ->>W: Deliver message
    W->>DB: Update status (processing)
    W->>W: Process application

    alt Success
        W->>DB: Update status (success)
    else Failure
        W->>DB: Update status (failed)
        W->>RMQ: Publish to DLQ
    end

    C->>API: GET /applications/{id}/status
    API->>DB: Query status
    API-->>C: 200 OK (status)
```

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB
- RabbitMQ
- Poetry (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/AIgen-Solutions-s-r-l/application-workflow-service.git
cd application-workflow-service

# Install with Poetry (recommended)
poetry install

# Or with pip
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
# Service
SERVICE_NAME=application_manager_service
ENVIRONMENT=development
DEBUG=True

# MongoDB
MONGODB=mongodb://localhost:27017
MONGODB_DATABASE=resumes

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
MIDDLEWARE_QUEUE=middleware_notification_queue
APPLICATION_PROCESSING_QUEUE=application_processing_queue
APPLICATION_DLQ=application_dlq

# Authentication
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Async Processing
ASYNC_PROCESSING_ENABLED=True

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_APPLICATIONS=100/hour
RATE_LIMIT_REQUESTS=1000/hour

# Retry
MAX_RETRIES=5
RETRY_BASE_DELAY=1.0
RETRY_MAX_DELAY=16.0
```

### Running the Service

```bash
# Start the API server
uvicorn app.main:app --reload --port 8009

# In a separate terminal, start the worker
python -m app.workers.application_worker
```

### Docker

```bash
# Build the image
docker build -t application-manager-service .

# Run with Docker Compose (includes MongoDB and RabbitMQ)
docker-compose up -d
```

## API Reference

### Authentication

All endpoints (except health checks) require JWT authentication:

```bash
curl -H "Authorization: Bearer <your_jwt_token>" ...
```

The JWT payload must contain an `id` field with the user ID.

### Endpoints

#### Submit Application

```bash
POST /applications
Content-Type: multipart/form-data

# Submit jobs with optional PDF resume
curl -X POST "http://localhost:8009/applications" \
  -H "Authorization: Bearer <token>" \
  -F 'jobs={"jobs":[{"id":"123","title":"Software Engineer","company_name":"Acme Corp","portal":"LinkedIn","description":"..."}]}' \
  -F 'style=modern' \
  -F 'cv=@resume.pdf'  # Optional
```

**Response:**
```json
{
  "application_id": "abc123def456",
  "status": "pending",
  "status_url": "/applications/abc123def456/status",
  "job_count": 1,
  "created_at": "2025-02-27T10:00:00Z"
}
```

#### Check Application Status

```bash
GET /applications/{application_id}/status

curl -H "Authorization: Bearer <token>" \
  "http://localhost:8009/applications/abc123def456/status"
```

**Response:**
```json
{
  "application_id": "abc123def456",
  "status": "processing",
  "created_at": "2025-02-27T10:00:00Z",
  "updated_at": "2025-02-27T10:05:00Z",
  "processed_at": null,
  "job_count": 1,
  "error_reason": null
}
```

#### List Successful Applications (Paginated)

```bash
GET /applied?limit=20&cursor=<cursor>&portal=LinkedIn&company_name=Google

curl -H "Authorization: Bearer <token>" \
  "http://localhost:8009/applied?limit=10&portal=LinkedIn"
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Items per page (1-100, default: 20) |
| `cursor` | string | Pagination cursor |
| `portal` | string | Filter by portal (exact match) |
| `company_name` | string | Filter by company (partial match) |
| `title` | string | Filter by title (partial match) |
| `date_from` | datetime | Filter from date (ISO 8601) |
| `date_to` | datetime | Filter until date (ISO 8601) |

**Response:**
```json
{
  "data": {
    "app_id_1": {"title": "...", "company_name": "...", ...},
    "app_id_2": {"title": "...", "company_name": "...", ...}
  },
  "pagination": {
    "limit": 20,
    "next_cursor": "eyJpZCI6IjEyMyJ9",
    "has_more": true,
    "total_count": 150
  }
}
```

#### Get Application Details

```bash
GET /applied/{app_id}
GET /fail_applied/{app_id}

# Returns resume_optimized and cover_letter for specific application
```

#### List Failed Applications

```bash
GET /fail_applied?limit=20&cursor=<cursor>
```

### Health Checks

```bash
# Kubernetes liveness probe
GET /health/live
# Response: {"status": "alive", "timestamp": "..."}

# Kubernetes readiness probe
GET /health/ready
# Response: {"status": "ready", "checks": {"mongodb": "ready", "rabbitmq": "ready"}}

# Full health check with details
GET /health
```

### Metrics

```bash
GET /metrics
# Returns Prometheus-formatted metrics
```

**Available Metrics:**
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_total` - Request counter by endpoint/status
- `applications_submitted_total` - Application submission counter
- `queue_messages_published_total` - Queue publish counter
- `dlq_messages_total` - Dead letter queue counter
- `rate_limit_exceeded_total` - Rate limit violations

## Advanced Features

### WebSocket Real-Time Updates

Get real-time status updates without polling:

```javascript
// Connect with JWT token
const ws = new WebSocket('ws://localhost:8009/ws/status?token=<jwt_token>');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data.type, data);  // "status_update", "batch_update", etc.
};
```

### Batch Operations

Submit multiple applications at once:

```bash
# Submit batch (up to 100 items)
curl -X POST "http://localhost:8009/batch/applications" \
  -H "Authorization: Bearer <token>" \
  -F 'items=[{"jobs":[...],"style":"modern"},{"jobs":[...],"style":"classic"}]' \
  -F 'cv=@shared_resume.pdf'

# Response: {"batch_id": "...", "status": "pending", "total": 2}

# Check progress
GET /batch/applications/{batch_id}

# Cancel batch
DELETE /batch/applications/{batch_id}
```

### Data Export

Export applications to CSV or Excel:

```bash
# Get export summary
GET /export/summary

# Download CSV
GET /export/csv?portal=LinkedIn&date_from=2025-01-01

# Download Excel (color-coded)
GET /export/excel

# Stream large datasets
GET /export/csv?stream=true
```

### Idempotency Keys

Prevent duplicate submissions using idempotency keys:

```bash
curl -X POST "http://localhost:8009/applications" \
  -H "X-Idempotency-Key: unique-request-id-123" \
  -H "Authorization: Bearer <token>" \
  ...
```

Duplicate requests (same key within 24 hours) return cached response with header:
```
X-Idempotency-Replayed: true
```

### Correlation IDs

Trace requests across services:

```bash
curl -H "X-Correlation-ID: my-trace-123" ...

# Response includes:
# X-Correlation-ID: my-trace-123
# X-Request-ID: my-trace-123
```

### Rate Limiting

Response headers include rate limit info:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1709035200
```

### Structured Errors

All errors follow a consistent format:

```json
{
  "error": "ApplicationNotFoundError",
  "code": "ERR_2001",
  "message": "Application not found: abc123",
  "correlation_id": "trace-456",
  "timestamp": "2025-02-27T10:00:00Z",
  "details": null
}
```

**Error Code Ranges:**
| Range | Category |
|-------|----------|
| ERR_1xxx | General (validation, not found) |
| ERR_2xxx | Application errors |
| ERR_3xxx | Job errors |
| ERR_4xxx | Resume errors |
| ERR_5xxx | Database errors |
| ERR_6xxx | Queue errors |
| ERR_7xxx | Rate limit errors |
| ERR_8xxx | Authentication errors |
| ERR_9xxx | Idempotency errors |

## Project Structure

```
application_manager_service/
├── app/
│   ├── cli/                  # Command-line interface
│   │   ├── commands/         # CLI command modules
│   │   │   ├── apps.py       # Application management
│   │   │   ├── config.py     # Configuration commands
│   │   │   ├── export.py     # Data export
│   │   │   ├── health.py     # Health checks
│   │   │   ├── metrics.py    # Metrics display
│   │   │   └── queue.py      # Queue management
│   │   ├── client.py         # HTTP client wrapper
│   │   ├── config.py         # CLI configuration
│   │   ├── main.py           # CLI entry point
│   │   └── output.py         # Rich output formatting
│   ├── core/                 # Core functionality
│   │   ├── auth.py           # JWT authentication
│   │   ├── config.py         # Configuration settings
│   │   ├── correlation.py    # Correlation ID middleware
│   │   ├── exceptions.py     # Structured error handling
│   │   ├── idempotency.py    # Idempotency key handling
│   │   ├── metrics.py        # Prometheus metrics
│   │   ├── mongo.py          # MongoDB client
│   │   ├── rabbitmq_client.py # RabbitMQ client
│   │   ├── rate_limit.py     # Rate limiting middleware
│   │   └── retry.py          # Retry with backoff
│   ├── models/               # Pydantic models
│   │   ├── application.py    # Application status models
│   │   └── job.py            # Job data models
│   ├── routers/              # API routes
│   │   ├── app_router.py     # Application endpoints
│   │   ├── healthcheck_router.py # Health probes
│   │   └── metrics_router.py # Prometheus endpoint
│   ├── schemas/              # Request/response schemas
│   │   └── app_jobs.py       # Job schemas, pagination
│   ├── services/             # Business logic
│   │   ├── application_uploader_service.py
│   │   ├── notification_service.py
│   │   ├── pdf_resume_service.py
│   │   └── queue_service.py
│   ├── workers/              # Background workers
│   │   └── application_worker.py
│   └── main.py               # FastAPI app entry point
├── tests/                    # Test suite
├── monitoring/               # SLO configs and dashboards
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## CLI Tool

The service includes a command-line interface for administration and monitoring.

### Installation

The CLI is installed automatically with the service:

```bash
# Using Poetry
poetry install

# Or install globally
pip install -e .
```

### Configuration

Configure the CLI using environment variables or a config file:

```bash
# Environment variables
export APP_MANAGER_API_URL=http://localhost:8009
export APP_MANAGER_API_TOKEN=your-jwt-token
export APP_MANAGER_API_TIMEOUT=30

# Or use the config command
app-manager config set api_url http://localhost:8009
app-manager config set api_token your-jwt-token
```

Configuration is stored in `~/.config/app-manager/config.env`.

### Commands

#### Health Checks

```bash
# Full health status
app-manager health

# Liveness check
app-manager health --live

# Readiness check
app-manager health --ready
```

#### Application Management

```bash
# List successful applications
app-manager apps list

# List failed applications
app-manager apps list --failed

# Filter by portal/company
app-manager apps list --portal LinkedIn --company Google

# Get application details
app-manager apps get <app_id>

# Check application status
app-manager apps status <app_id>

# Retry a failed application
app-manager apps retry <app_id>

# Cancel a pending application
app-manager apps cancel <app_id>
```

#### Queue Management

```bash
# View queue status
app-manager queue status

# Purge dead letter queue
app-manager queue purge-dlq --force

# Reprocess DLQ messages
app-manager queue reprocess-dlq
```

#### Data Export

```bash
# Export to CSV
app-manager export csv --output applications.csv

# Export to Excel
app-manager export excel --output applications.xlsx

# Filter exports
app-manager export csv --portal LinkedIn --from 2025-01-01 --to 2025-12-31

# View export summary
app-manager export summary
```

#### Metrics

```bash
# View metrics summary
app-manager metrics

# Raw Prometheus format
app-manager metrics --raw

# Filter specific metrics
app-manager metrics --filter http_requests
```

#### Configuration Management

```bash
# Show current config
app-manager config show

# Set a value
app-manager config set api_url http://production:8009

# Get a value
app-manager config get api_url

# Reset to defaults
app-manager config reset --force
```

### Output Formats

Use `--json` flag for JSON output (useful for scripting):

```bash
app-manager apps list --json | jq '.data'
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing --cov-report=html

# Run specific test file
pytest tests/services/test_application_uploader_service.py

# Run tests matching a pattern
pytest -k "application"
```

## Monitoring & Observability

### SLO Targets

Defined in `monitoring/slo-config.yaml`:

| SLO | Target | Window |
|-----|--------|--------|
| Availability | 99.9% | 30 days |
| Latency P95 | < 500ms | - |
| Latency P99 | < 2s | - |
| Processing Success | 99% | - |

### Grafana Dashboard

Import the dashboard configuration from `monitoring/slo-config.yaml` into Grafana for:
- Request rate and latency panels
- Error rate tracking
- Queue depth monitoring
- SLO burn rate alerts

### Distributed Tracing

OpenTelemetry tracing with Jaeger/OTLP support:

```env
TRACING_ENABLED=true
TRACING_EXPORTER=jaeger
JAEGER_HOST=localhost
JAEGER_PORT=6831
```

### Alerting Rules

Pre-configured Prometheus alerts in `monitoring/prometheus-alerts.yaml`:
- Service availability and error rates
- Latency SLO violations
- Application processing health
- Queue and database issues
- Resource utilization

### Log Aggregation

Loki/Promtail configuration in `monitoring/loki-config.yaml`:
- JSON log parsing with label extraction
- Pre-built LogQL queries
- Log-based alerting rules

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with FastAPI, MongoDB, and RabbitMQ
</p>
