"""
Load test configuration and thresholds.
"""

import os

# Target service URL
BASE_URL = os.getenv("LOAD_TEST_BASE_URL", "http://localhost:8009")

# Authentication
AUTH_SECRET_KEY = os.getenv("LOAD_TEST_SECRET_KEY", "test-secret-key")
AUTH_ALGORITHM = "HS256"

# Test user configuration
TEST_USER_ID = "load_test_user_001"

# Performance thresholds
THRESHOLDS = {
    # Response time thresholds (milliseconds)
    "p50_response_time_ms": 100,
    "p95_response_time_ms": 500,
    "p99_response_time_ms": 2000,

    # Error rate threshold (percentage)
    "error_rate_percent": 1.0,

    # Minimum requests per second
    "min_rps": 100,

    # Per-endpoint thresholds
    "endpoints": {
        "POST /applications": {
            "p95_ms": 300,
            "p99_ms": 500,
        },
        "GET /applications/{id}/status": {
            "p95_ms": 50,
            "p99_ms": 100,
        },
        "GET /applied": {
            "p95_ms": 150,
            "p99_ms": 300,
        },
        "GET /health": {
            "p95_ms": 10,
            "p99_ms": 20,
        },
        "GET /health/live": {
            "p95_ms": 10,
            "p99_ms": 20,
        },
        "GET /health/ready": {
            "p95_ms": 50,
            "p99_ms": 100,
        },
    },
}

# Test scenarios
SCENARIOS = {
    "baseline": {
        "users": 10,
        "spawn_rate": 2,
        "duration": "5m",
        "description": "Establish baseline metrics",
    },
    "normal": {
        "users": 100,
        "spawn_rate": 10,
        "duration": "15m",
        "description": "Typical production load",
    },
    "peak": {
        "users": 500,
        "spawn_rate": 50,
        "duration": "10m",
        "description": "Peak traffic simulation",
    },
    "spike": {
        "users": 1000,
        "spawn_rate": 200,
        "duration": "5m",
        "description": "Sudden traffic burst",
    },
    "endurance": {
        "users": 100,
        "spawn_rate": 10,
        "duration": "4h",
        "description": "Long-term stability test",
    },
}

# Task weights (relative frequency)
TASK_WEIGHTS = {
    "submit_application": 3,
    "check_status": 5,
    "list_applications": 2,
    "get_application_detail": 2,
    "health_check": 1,
}
