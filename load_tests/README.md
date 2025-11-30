# Load Testing Suite

This directory contains load testing configuration for the Application Manager Service using [Locust](https://locust.io/).

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for full stack testing)
- Poetry (for dependency management)

### Install Dependencies

```bash
# From the project root
poetry install

# Or install locust directly
pip install locust python-jose
```

### Run Load Tests Locally

**Option 1: Against a running service**

```bash
# Start the application first
uvicorn app.main:app --port 8009

# In another terminal, run load tests
cd load_tests
locust -f locustfile.py --host http://localhost:8009
```

Open http://localhost:8089 for the Locust web UI.

**Option 2: Headless mode**

```bash
cd load_tests
locust -f locustfile.py \
  --host http://localhost:8009 \
  --headless \
  -u 100 \
  -r 10 \
  -t 5m \
  --html report.html
```

### Run with Docker Compose (Full Stack)

This runs the complete stack including MongoDB, RabbitMQ, Redis, and monitoring:

```bash
cd load_tests
docker-compose up -d

# Access services:
# - Locust Web UI: http://localhost:8089
# - Application: http://localhost:8009
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
# - RabbitMQ Management: http://localhost:15672 (guest/guest)
```

To stop:

```bash
docker-compose down -v
```

## Test Scenarios

### Standard Load Test

Simulates typical user behavior with mixed operations:

| Parameter | Value |
|-----------|-------|
| Users | 100 |
| Spawn Rate | 10/s |
| Duration | 5-10 min |

```bash
locust -f locustfile.py --headless -u 100 -r 10 -t 5m
```

### Spike Test

Tests system behavior under sudden load increase:

| Parameter | Value |
|-----------|-------|
| Users | 500 |
| Spawn Rate | 50/s |
| Duration | 2 min |

```bash
locust -f locustfile.py --headless -u 500 -r 50 -t 2m
```

### Soak Test

Tests system stability over extended period:

| Parameter | Value |
|-----------|-------|
| Users | 50 |
| Spawn Rate | 5/s |
| Duration | 30 min |

```bash
locust -f locustfile.py --headless -u 50 -r 5 -t 30m
```

### Stress Test

Finds breaking point by gradually increasing load:

| Parameter | Value |
|-----------|-------|
| Users | 1000 |
| Spawn Rate | 100/s |
| Duration | 10 min |

```bash
locust -f locustfile.py --headless -u 1000 -r 100 -t 10m
```

## User Classes

The load test includes three user types:

### ApplicationManagerUser (Weight: 10)

Standard user behavior:
- Submit applications (30%)
- Check application status (40%)
- List applications (15%)
- Get application details (10%)
- Health checks (5%)

### HighFrequencyStatusChecker (Weight: 2)

Simulates monitoring dashboards:
- 10 status checks per second
- Occasional health checks

### BurstSubmitter (Weight: 1)

Simulates batch imports:
- Submits 3-10 applications in quick succession
- 5-10 second wait between bursts

## Thresholds

Performance thresholds are defined in `config.py`:

| Metric | Standard | Spike | Soak | Stress |
|--------|----------|-------|------|--------|
| Error Rate | < 1% | < 5% | < 0.5% | < 10% |
| P95 Latency | < 500ms | < 2000ms | < 500ms | < 5000ms |
| P99 Latency | < 2000ms | < 5000ms | < 1000ms | < 10000ms |
| Min RPS | 50 | 100 | 30 | 200 |

### Check Thresholds

After running a test, verify thresholds:

```bash
python check_thresholds.py --csv-prefix results --scenario standard
```

## Directory Structure

```
load_tests/
├── locustfile.py           # Main Locust configuration
├── config.py               # Thresholds and test settings
├── check_thresholds.py     # Post-test threshold validator
├── docker-compose.yaml     # Full stack for testing
├── prometheus.yaml         # Prometheus config
├── tasks/                  # Task modules
│   ├── __init__.py
│   ├── applications.py     # Application submission tasks
│   ├── health.py           # Health check tasks
│   ├── listing.py          # Listing and pagination tasks
│   └── status.py           # Status check tasks
├── data/                   # Test data
│   └── sample_jobs.json    # Sample job data
└── grafana/               # Grafana dashboards
    └── provisioning/
        ├── datasources/
        └── dashboards/
```

## CI/CD Integration

Load tests run automatically via GitHub Actions:

- **Scheduled**: Weekly on Sundays at 2 AM UTC
- **Manual**: Trigger via workflow_dispatch with custom parameters
- **On Release**: Optionally enable for release tags

### Manual Trigger

1. Go to Actions → Load Tests
2. Click "Run workflow"
3. Configure:
   - Users: 50-500
   - Spawn Rate: 5-50
   - Duration: 5m-30m
   - Scenario: standard/spike/soak/stress

### Results

Test artifacts are uploaded to GitHub Actions:
- `report.html` - Visual HTML report
- `results_*.csv` - Raw CSV data
- `threshold_report.json` - Threshold check results

## Monitoring During Tests

### Grafana Dashboard

Access http://localhost:3000 (admin/admin) for:
- Request latency (P95/P99)
- Requests per second by status code
- Error rate
- Queue message rates
- DLQ messages

### Prometheus Queries

```promql
# Request rate
sum(rate(http_requests_total[1m]))

# Error rate
sum(rate(http_requests_total{status_code=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))

# P95 latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))

# Application submission rate
sum(rate(applications_submitted_total[1m]))
```

## Troubleshooting

### Connection Refused

Ensure the application is running and accessible:

```bash
curl http://localhost:8009/health/live
```

### Authentication Errors

The tests generate JWT tokens automatically. Ensure:
- `AUTH_SECRET_KEY` matches between test config and application
- `AUTH_ALGORITHM` is set to `HS256`

### Rate Limit Errors

For load testing, disable rate limiting:

```bash
export RATE_LIMIT_ENABLED=false
```

### High Error Rates

Check application logs:

```bash
docker-compose logs app -f
```

Check worker logs:

```bash
docker-compose logs worker -f
```

## Scaling Workers

For distributed load testing, scale Locust workers:

```bash
docker-compose up -d --scale locust-worker=8
```

For application workers:

```bash
docker-compose up -d --scale worker=4
```
