# Application Manager Service

<p align="center">
  <img src="https://img.shields.io/badge/version-1.5.0-brightgreen.svg" alt="Version 1.5.0"/>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/MongoDB-Motor-47A248.svg" alt="MongoDB"/>
  <img src="https://img.shields.io/badge/Redis-Cluster-DC382D.svg" alt="Redis"/>
  <img src="https://img.shields.io/badge/RabbitMQ-aio--pika-FF6600.svg" alt="RabbitMQ"/>
  <img src="https://img.shields.io/badge/OpenTelemetry-tracing-blue.svg" alt="OpenTelemetry"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"/>
</p>

<p align="center">
  <b>Production-grade microservice for high-throughput job application workflows</b><br/>
  <i>Event-driven architecture • Real-time processing • Enterprise observability</i>
</p>

---

## Overview

A distributed microservice engineered to handle complex job application workflows at scale. The system processes thousands of concurrent applications through an event-driven pipeline, maintaining consistency across distributed components while providing real-time visibility into every operation.

The architecture embraces cloud-native principles: stateless API servers scale horizontally, background workers process asynchronously from durable queues, and a distributed cache layer minimizes database pressure during traffic spikes.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INGRESS LAYER                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Rate Limit  │→ │ Auth (JWT)  │→ │ Correlation │→ │ Security Headers (OWASP)│ │
│  │ Middleware  │  │ Middleware  │  │ ID Tracking │  │ CSP, HSTS, XSS, etc.    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                           API GATEWAY (FastAPI)                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────────────┐  │
│  │   REST API v1    │  │   REST API v2    │  │   WebSocket (Real-time)       │  │
│  │   /v1/*          │  │   /v2/* (HATEOAS)│  │   /ws/status                  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────────────┬───────────────┘  │
│           │     API Versioning with Deprecation Headers      │                  │
└───────────┼──────────────────────────────────────────────────┼──────────────────┘
            │                                                  │
┌───────────▼──────────────────────────────────────────────────▼──────────────────┐
│                          SERVICE LAYER                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  Application    │  │   Webhook       │  │   Admin         │                  │
│  │  Service        │  │   Service       │  │   Service       │                  │
│  │  ─────────────  │  │   ─────────────  │  │   ─────────────  │                  │
│  │  • CRUD ops     │  │  • Event fanout │  │  • Analytics    │                  │
│  │  • Status FSM   │  │  • HMAC signing │  │  • User mgmt    │                  │
│  │  • Idempotency  │  │  • Retry w/     │  │  • Audit logs   │                  │
│  │                 │  │    backoff      │  │  • RBAC         │                  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                  │
└───────────┼────────────────────┼────────────────────┼────────────────────────────┘
            │                    │                    │
┌───────────▼────────────────────▼────────────────────▼────────────────────────────┐
│                        ASYNC PROCESSING LAYER                                    │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                        RabbitMQ (Message Broker)                         │   │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐  │   │
│   │  │ Processing     │  │ Notification   │  │ Dead Letter Queue          │  │   │
│   │  │ Queue          │  │ Queue          │  │ (Failed message handling)  │  │   │
│   │  └───────┬────────┘  └───────┬────────┘  └────────────────────────────┘  │   │
│   └──────────┼───────────────────┼───────────────────────────────────────────┘   │
│              │                   │                                               │
│   ┌──────────▼───────────────────▼───────────────────────────────────────────┐   │
│   │                      Background Workers                                  │   │
│   │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐   │   │
│   │  │ Application     │  │ Webhook         │  │ Scheduler (APScheduler) │   │   │
│   │  │ Worker          │  │ Dispatcher      │  │ ───────────────────────  │   │   │
│   │  │ ───────────────  │  │ ───────────────  │  │ • Cleanup jobs         │   │   │
│   │  │ • Process jobs  │  │ • HTTP delivery │  │ • Health monitoring    │   │   │
│   │  │ • Retry logic   │  │ • Exp. backoff  │  │ • DLQ alerts           │   │   │
│   │  │ • DLQ routing   │  │ • Circuit break │  │ • Cron scheduling      │   │   │
│   │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘   │   │
│   └──────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                            DATA LAYER                                           │
│                                                                                 │
│  ┌───────────────────────────────────┐  ┌─────────────────────────────────────┐ │
│  │           MongoDB                 │  │              Redis                  │ │
│  │  ─────────────────────────────────│  │  ───────────────────────────────────│ │
│  │  • Primary data store             │  │  • Distributed cache                │ │
│  │  • Optimized indexes              │  │  • Rate limit counters              │ │
│  │  • TTL collections                │  │  • Session storage                  │ │
│  │  • Change streams                 │  │  • Circuit breaker state            │ │
│  │  • Connection pooling (10-100)    │  │  • Automatic failover               │ │
│  └───────────────────────────────────┘  └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                         OBSERVABILITY STACK                                     │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Prometheus    │  │  OpenTelemetry  │  │      Loki       │  │   Grafana   │ │
│  │   ───────────── │  │  ─────────────── │  │  ─────────────── │  │  ───────────│ │
│  │   • Metrics     │  │  • Distributed  │  │  • Log          │  │  • Unified  │ │
│  │   • Alerts      │  │    tracing      │  │    aggregation  │  │    dashboards│ │
│  │   • SLO burn    │  │  • Jaeger/OTLP  │  │  • LogQL        │  │  • SLO      │ │
│  │     rate        │  │  • Auto-instr.  │  │  • Alerting     │  │    tracking │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Core Capabilities

### Event-Driven Application Processing

Applications flow through a state machine with well-defined transitions. Each state change triggers events that propagate through the system - updating caches, notifying webhooks, and recording audit trails.

```
                    ┌─────────────────────────────────────────────┐
                    │           APPLICATION LIFECYCLE             │
                    └─────────────────────────────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────────┐
                    │                 PENDING                     │
                    │  • Idempotency check passed                 │
                    │  • Queued in RabbitMQ                       │
                    │  • WebSocket notification sent              │
                    └────────────────────┬────────────────────────┘
                                         │ Worker picks up
                    ┌────────────────────▼────────────────────────┐
                    │               PROCESSING                    │
                    │  • Worker acquired lock                     │
                    │  • Business logic executing                 │
                    │  • Progress tracked in real-time            │
                    └────────────────────┬────────────────────────┘
                                         │
                         ┌───────────────┴───────────────┐
                         │                               │
            ┌────────────▼────────────┐    ┌─────────────▼───────────┐
            │        SUCCESS          │    │         FAILED          │
            │  • Moved to success_app │    │  • Error reason stored  │
            │  • Webhooks triggered   │    │  • Routed to DLQ        │
            │  • Cache invalidated    │    │  • Alert if threshold   │
            └─────────────────────────┘    └─────────────────────────┘
```

### Distributed Caching with Circuit Breaker

The caching layer uses Redis as the primary store with automatic fallback to in-memory cache. A circuit breaker monitors Redis health and seamlessly switches traffic during outages.

```
Request ──▶ ┌─────────────────────────────────────────────────────────────────┐
            │                    CACHE LAYER                                  │
            │                                                                 │
            │   ┌─────────────┐     Circuit State     ┌─────────────────────┐ │
            │   │             │◀────── CLOSED ───────▶│       Redis         │ │
            │   │   Circuit   │                       │  (Primary Cache)    │ │
            │   │   Breaker   │◀────── OPEN ─────────▶│         │           │ │
            │   │             │                       │         ▼           │ │
            │   │  ┌────────┐ │     Failure Count     │   ┌──────────┐      │ │
            │   │  │ 5 fail │ │────── > 5 ──────────▶ │   │ Fallback │      │ │
            │   │  │ = open │ │                       │   │ Memory   │      │ │
            │   │  └────────┘ │◀──── HALF-OPEN ─────▶ │   │ Cache    │      │ │
            │   │             │     (test request)    │   └──────────┘      │ │
            │   └─────────────┘                       └─────────────────────┘ │
            └─────────────────────────────────────────────────────────────────┘
```

### API Versioning Strategy

Two API versions coexist, enabling gradual migration. v1 serves current integrations while v2 introduces HATEOAS, improved pagination, and a cleaner response structure. Deprecation headers guide clients toward migration.

| Aspect | v1 (Current) | v2 (Next Generation) |
|--------|--------------|----------------------|
| Response IDs | `application_id` | `id` |
| Status | String value | Object with metadata |
| Pagination | Body-based cursors | Header-based (RFC 8288) |
| Navigation | Manual URL construction | HATEOAS `_links` |
| Deprecation | Sunset headers when announced | - |

### Webhook System

External systems receive real-time notifications through a reliable webhook delivery pipeline. Messages are signed with HMAC-SHA256 for authenticity, and failed deliveries automatically retry with exponential backoff.

```
Event Triggered
      │
      ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Build Payload  │────▶│  Sign (HMAC)    │────▶│  Deliver (HTTP) │
│  + timestamp    │     │  SHA256 + secret│     │  POST to URL    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌────────────────────────────────┴────────┐
                        │                                         │
               ┌────────▼────────┐                    ┌───────────▼──────────┐
               │    Success      │                    │      Failed          │
               │  (2xx response) │                    │  (timeout/5xx/etc)   │
               └────────┬────────┘                    └───────────┬──────────┘
                        │                                         │
               ┌────────▼────────┐                    ┌───────────▼──────────┐
               │ Record delivery │                    │  Schedule retry      │
               │ history (30d)   │                    │  1m → 5m → 15m → 1h  │
               └─────────────────┘                    └───────────┬──────────┘
                                                                  │
                                                      ┌───────────▼──────────┐
                                                      │ 10 consecutive fails │
                                                      │ → Auto-disable hook  │
                                                      └──────────────────────┘
```

### Background Job Scheduler

Maintenance tasks run automatically through APScheduler. Jobs are persisted, tracked, and exposed through both API and CLI for operational visibility.

| Job | Schedule | Purpose |
|-----|----------|---------|
| `cleanup_old_applications` | Daily 02:00 | Remove applications past retention |
| `cleanup_expired_idempotency` | Hourly | Purge expired idempotency keys |
| `cleanup_old_webhook_deliveries` | Daily 03:00 | Trim webhook delivery history |
| `deep_health_check` | Every 5 min | Comprehensive dependency check |
| `dlq_alert_check` | Every 10 min | Alert on DLQ message buildup |

### Admin Dashboard & RBAC

Three-tier role-based access controls administrative functions:

```
                    ┌─────────────────────────────────────────┐
                    │              ADMIN ROLES                │
                    └─────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
┌───────▼───────┐            ┌─────────▼─────────┐          ┌─────────▼─────────┐
│    VIEWER     │            │     OPERATOR      │          │      ADMIN        │
│ ───────────── │            │ ─────────────────  │          │ ─────────────────  │
│ • Dashboard   │            │ • All VIEWER +    │          │ • All OPERATOR + │
│ • Analytics   │            │ • Pause/resume    │          │ • System config  │
│ • Job status  │            │   scheduled jobs  │          │ • User actions   │
│ • User list   │            │ • Trigger jobs    │          │ • Queue purge    │
│ • Audit view  │            │ • Reset limits    │          │ • Full audit     │
└───────────────┘            └───────────────────┘          └───────────────────┘
```

## Observability

### Metrics (Prometheus)

Every significant operation emits metrics. Custom business metrics complement standard HTTP instrumentation:

```
# Request latency distribution
http_request_duration_seconds_bucket{endpoint="/v1/applications",le="0.5"} 1847
http_request_duration_seconds_bucket{endpoint="/v1/applications",le="1.0"} 1892

# Application processing
applications_submitted_total{status="success"} 15234
applications_submitted_total{status="failed"} 127

# Queue health
queue_messages_published_total{queue="processing"} 15361
dlq_messages_total 45

# Cache performance
cache_operations_total{operation="get",status="hit"} 89234
cache_operations_total{operation="get",status="miss"} 3421
cache_circuit_breaker_state 0  # 0=closed, 1=open, 2=half_open

# Rate limiting
rate_limit_exceeded_total{endpoint="/applications"} 23
```

### Distributed Tracing (OpenTelemetry)

Traces follow requests across service boundaries. Each span captures timing, metadata, and relationships:

```
Trace: a]8f2c-4e3d-9b1a-7c6d5e4f3a2b
│
├─ HTTP POST /v1/applications (245ms)
│  ├─ validate_request (12ms)
│  ├─ check_idempotency (8ms) [cache: hit]
│  ├─ store_application (45ms) [mongodb]
│  ├─ publish_to_queue (15ms) [rabbitmq]
│  └─ broadcast_websocket (3ms)
│
└─ Worker: process_application (180ms)
   ├─ acquire_lock (5ms)
   ├─ execute_business_logic (150ms)
   ├─ update_status (15ms) [mongodb]
   └─ trigger_webhooks (10ms)
```

### SLO Targets

| Objective | Target | Measurement |
|-----------|--------|-------------|
| Availability | 99.9% | Non-5xx responses / total |
| Latency P95 | < 500ms | 95th percentile |
| Latency P99 | < 2s | 99th percentile |
| Processing Success | 99% | Success / total applications |
| Error Budget Burn | < 2x | Hourly burn rate |

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB 5.0+
- RabbitMQ 3.11+
- Redis 7.0+ (optional, falls back to memory)

### Installation

```bash
git clone https://github.com/AIgen-Solutions-s-r-l/application-workflow-service.git
cd application-workflow-service

# Install dependencies
poetry install  # or: pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Run the Service

```bash
# Start API server (development)
uvicorn app.main:app --reload --port 8009

# Start background worker
python -m app.workers.application_worker
```

### Docker Compose (Full Stack)

```bash
docker-compose up -d
# Starts: API, Worker, MongoDB, RabbitMQ, Redis
```

## API Quick Reference

### Submit Application

```bash
curl -X POST "http://localhost:8009/v1/applications" \
  -H "Authorization: Bearer <token>" \
  -H "X-Idempotency-Key: unique-id-123" \
  -F 'jobs={"jobs":[{"title":"Engineer","company_name":"Acme"}]}' \
  -F 'cv=@resume.pdf'
```

### Check Status

```bash
curl "http://localhost:8009/v1/applications/{id}/status" \
  -H "Authorization: Bearer <token>"
```

### WebSocket (Real-time Updates)

```javascript
const ws = new WebSocket('ws://localhost:8009/ws/status?token=<jwt>');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### List Applications (Paginated)

```bash
curl "http://localhost:8009/v1/applied?limit=20&portal=LinkedIn" \
  -H "Authorization: Bearer <token>"
```

## CLI Tool

```bash
# Health check
app-manager health

# List applications
app-manager apps list --portal LinkedIn --limit 50

# Export data
app-manager export csv --output applications.csv

# Scheduler management
app-manager scheduler list
app-manager scheduler run cleanup_old_applications

# Admin dashboard
app-manager admin dashboard
app-manager admin analytics apps --period week
```

## Configuration Reference

```env
# Core
SERVICE_NAME=application_manager_service
ENVIRONMENT=production

# Database
MONGODB=mongodb://localhost:27017
MONGODB_DATABASE=resumes
MONGO_MAX_POOL_SIZE=100

# Cache
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
CACHE_FALLBACK_TO_MEMORY=true

# Queue
RABBITMQ_URL=amqp://localhost:5672/
ASYNC_PROCESSING_ENABLED=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=1000/hour

# Observability
TRACING_ENABLED=true
TRACING_EXPORTER=otlp
OTLP_ENDPOINT=http://localhost:4317

# Scheduler
SCHEDULER_ENABLED=true
CLEANUP_RETENTION_DAYS=90

# Security
SECRET_KEY=<your-secret>
WEBHOOK_REQUIRE_HTTPS=true
ADMIN_ENABLED=true
```

## Project Structure

```
application_manager_service/
├── app/
│   ├── cli/                    # Command-line interface
│   │   └── commands/           # CLI command modules
│   ├── core/                   # Infrastructure layer
│   │   ├── admin_auth.py       # RBAC implementation
│   │   ├── cache.py            # Redis + circuit breaker
│   │   ├── correlation.py      # Distributed tracing context
│   │   ├── idempotency.py      # Duplicate request handling
│   │   ├── rate_limit.py       # Token bucket rate limiter
│   │   └── tracing.py          # OpenTelemetry integration
│   ├── migrations/             # Schema migration system
│   ├── models/                 # Domain models
│   ├── routers/                # API endpoints (v1, v2)
│   ├── scheduler/              # Background job definitions
│   │   └── jobs/               # Cleanup, monitoring tasks
│   ├── services/               # Business logic
│   └── workers/                # Queue consumers
├── tests/                      # Test suite (pytest)
├── monitoring/                 # Prometheus alerts, Grafana dashboards
├── k8s/                        # Kubernetes manifests
└── load-tests/                 # Locust performance tests
```

## Testing

```bash
# Unit + integration tests
pytest

# With coverage report
pytest --cov=app --cov-report=html

# Load testing
locust -f load-tests/locustfile.py --host=http://localhost:8009
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Engineered for reliability at scale</sub>
</p>
