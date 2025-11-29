"""
Tests for Sprint 3 features:
- Story #16: Prometheus metrics endpoint
- Story #17: Correlation IDs for request tracing
- Story #18: Dead-letter queue (already tested in Sprint 2)
- Story #19: Filtering parameters for list endpoints
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.correlation import (
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
    get_correlation_headers,
    add_correlation_to_message,
    extract_correlation_from_message,
    CORRELATION_ID_HEADER
)
from app.core.metrics import (
    get_metrics,
    get_metrics_content_type,
    record_application_submitted,
    record_queue_publish,
    record_dlq_message,
    record_rate_limit_exceeded,
    record_worker_retry,
    set_worker_active,
    MetricsMiddleware
)
from app.schemas.app_jobs import FilterParams, PaginationParams
from app.routers.app_router import apply_filters


class TestPrometheusMetrics:
    """Tests for Story #16: Prometheus metrics endpoint."""

    def test_get_metrics_returns_bytes(self):
        """Verify get_metrics returns byte content."""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)

    def test_get_metrics_content_type(self):
        """Verify metrics content type is correct."""
        content_type = get_metrics_content_type()
        assert "text/plain" in content_type or "text/openmetrics" in content_type

    def test_record_application_submitted(self):
        """Verify application submission metric is recorded."""
        # Should not raise
        record_application_submitted(user_type='authenticated')
        record_application_submitted(user_type='anonymous')

    def test_record_queue_publish(self):
        """Verify queue publish metric is recorded."""
        record_queue_publish('test_queue')

    def test_record_dlq_message(self):
        """Verify DLQ message metric is recorded."""
        record_dlq_message('original_queue', 'ValueError')

    def test_record_rate_limit_exceeded(self):
        """Verify rate limit exceeded metric is recorded."""
        record_rate_limit_exceeded('/applications', 'authenticated')

    def test_record_worker_retry(self):
        """Verify worker retry metric is recorded."""
        record_worker_retry('application_worker', 1)
        record_worker_retry('application_worker', 2)

    def test_set_worker_active(self):
        """Verify worker active gauge is set."""
        set_worker_active('application_worker', True)
        set_worker_active('application_worker', False)

    def test_metrics_middleware_normalize_path(self):
        """Verify path normalization replaces IDs with placeholders."""
        middleware = MetricsMiddleware(app=MagicMock())

        # ObjectId-like path
        path = "/applications/507f1f77bcf86cd799439011/status"
        normalized = middleware._normalize_path(path)
        assert normalized == "/applications/{id}/status"

        # UUID-like path
        path = "/applied/123e4567-e89b-12d3-a456-426614174000"
        normalized = middleware._normalize_path(path)
        assert normalized == "/applied/{id}"

        # Root path
        assert middleware._normalize_path("/") == "/"

        # Regular path without IDs
        assert middleware._normalize_path("/health") == "/health"


class TestCorrelationId:
    """Tests for Story #17: Correlation IDs for request tracing."""

    def test_generate_correlation_id(self):
        """Verify correlation ID generation produces valid UUID."""
        correlation_id = generate_correlation_id()
        assert isinstance(correlation_id, str)
        # Should be a valid UUID
        uuid.UUID(correlation_id)

    def test_set_and_get_correlation_id(self):
        """Verify correlation ID can be set and retrieved."""
        test_id = "test-correlation-123"
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id

    def test_get_correlation_headers(self):
        """Verify correlation headers are generated correctly."""
        test_id = "test-correlation-456"
        set_correlation_id(test_id)

        headers = get_correlation_headers()
        assert CORRELATION_ID_HEADER in headers
        assert headers[CORRELATION_ID_HEADER] == test_id

    def test_get_correlation_headers_when_not_set(self):
        """Verify empty headers when no correlation ID is set."""
        # Reset the context var
        from app.core.correlation import correlation_id_var
        correlation_id_var.set(None)

        headers = get_correlation_headers()
        assert headers == {}

    def test_add_correlation_to_message(self):
        """Verify correlation ID is added to messages."""
        test_id = "test-correlation-789"
        set_correlation_id(test_id)

        message = {"application_id": "app_123"}
        enriched = add_correlation_to_message(message)

        assert "correlation_id" in enriched
        assert enriched["correlation_id"] == test_id
        assert enriched["application_id"] == "app_123"

    def test_extract_correlation_from_message(self):
        """Verify correlation ID is extracted and set from message."""
        message = {
            "application_id": "app_123",
            "correlation_id": "extracted-correlation-id"
        }

        result = extract_correlation_from_message(message)

        assert result == "extracted-correlation-id"
        assert get_correlation_id() == "extracted-correlation-id"

    def test_extract_correlation_from_message_without_id(self):
        """Verify None is returned when message has no correlation ID."""
        message = {"application_id": "app_123"}

        result = extract_correlation_from_message(message)

        assert result is None


class TestFilterParams:
    """Tests for Story #19: Filtering parameters."""

    def test_filter_params_defaults(self):
        """Verify FilterParams has all None defaults."""
        params = FilterParams()
        assert params.portal is None
        assert params.company_name is None
        assert params.title is None
        assert params.date_from is None
        assert params.date_to is None

    def test_filter_params_with_values(self):
        """Verify FilterParams accepts values."""
        now = datetime.utcnow()
        params = FilterParams(
            portal="LinkedIn",
            company_name="Test Corp",
            title="Engineer",
            date_from=now,
            date_to=now
        )

        assert params.portal == "LinkedIn"
        assert params.company_name == "Test Corp"
        assert params.title == "Engineer"
        assert params.date_from == now
        assert params.date_to == now


class TestApplyFilters:
    """Tests for apply_filters function."""

    def test_apply_filters_no_filters(self):
        """Verify content is returned unchanged when no filters."""
        content = {
            "app1": {"title": "Engineer", "portal": "LinkedIn"},
            "app2": {"title": "Manager", "portal": "Indeed"}
        }
        filters = FilterParams()

        result = apply_filters(content, filters)

        assert result == content

    def test_apply_filters_by_portal(self):
        """Verify portal filter works (exact match, case-insensitive)."""
        content = {
            "app1": {"title": "Engineer", "portal": "LinkedIn"},
            "app2": {"title": "Manager", "portal": "Indeed"},
            "app3": {"title": "Designer", "portal": "linkedin"}
        }
        filters = FilterParams(portal="linkedin")

        result = apply_filters(content, filters)

        assert len(result) == 2
        assert "app1" in result
        assert "app3" in result
        assert "app2" not in result

    def test_apply_filters_by_company_name(self):
        """Verify company name filter works (partial match)."""
        content = {
            "app1": {"title": "Engineer", "company_name": "Google Inc"},
            "app2": {"title": "Manager", "company_name": "Microsoft"},
            "app3": {"title": "Designer", "company_name": "Google Cloud"}
        }
        filters = FilterParams(company_name="google")

        result = apply_filters(content, filters)

        assert len(result) == 2
        assert "app1" in result
        assert "app3" in result

    def test_apply_filters_by_title(self):
        """Verify title filter works (partial match)."""
        content = {
            "app1": {"title": "Software Engineer", "portal": "LinkedIn"},
            "app2": {"title": "Project Manager", "portal": "Indeed"},
            "app3": {"title": "Senior Engineer", "portal": "Glassdoor"}
        }
        filters = FilterParams(title="engineer")

        result = apply_filters(content, filters)

        assert len(result) == 2
        assert "app1" in result
        assert "app3" in result

    def test_apply_filters_by_date_from(self):
        """Verify date_from filter works."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        content = {
            "app1": {"title": "Engineer", "created_at": now.isoformat()},
            "app2": {"title": "Manager", "created_at": yesterday.isoformat()},
            "app3": {"title": "Designer", "created_at": last_week.isoformat()}
        }
        filters = FilterParams(date_from=yesterday)

        result = apply_filters(content, filters)

        assert len(result) == 2
        assert "app1" in result
        assert "app2" in result
        assert "app3" not in result

    def test_apply_filters_by_date_to(self):
        """Verify date_to filter works."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        content = {
            "app1": {"title": "Engineer", "created_at": now.isoformat()},
            "app2": {"title": "Manager", "created_at": yesterday.isoformat()},
            "app3": {"title": "Designer", "created_at": last_week.isoformat()}
        }
        filters = FilterParams(date_to=yesterday)

        result = apply_filters(content, filters)

        assert len(result) == 2
        assert "app2" in result
        assert "app3" in result
        assert "app1" not in result

    def test_apply_filters_combined(self):
        """Verify multiple filters work together (AND logic)."""
        content = {
            "app1": {"title": "Software Engineer", "portal": "LinkedIn", "company_name": "Google"},
            "app2": {"title": "Software Engineer", "portal": "Indeed", "company_name": "Google"},
            "app3": {"title": "Project Manager", "portal": "LinkedIn", "company_name": "Google"},
            "app4": {"title": "Software Engineer", "portal": "LinkedIn", "company_name": "Microsoft"}
        }
        filters = FilterParams(portal="LinkedIn", title="engineer")

        result = apply_filters(content, filters)

        assert len(result) == 2
        assert "app1" in result
        assert "app4" in result

    def test_apply_filters_empty_result(self):
        """Verify empty result when no items match filters."""
        content = {
            "app1": {"title": "Engineer", "portal": "LinkedIn"},
            "app2": {"title": "Manager", "portal": "Indeed"}
        }
        filters = FilterParams(portal="Glassdoor")

        result = apply_filters(content, filters)

        assert result == {}

    def test_apply_filters_with_iso_date_string_z_suffix(self):
        """Verify date parsing handles Z suffix."""
        now = datetime.utcnow()

        content = {
            "app1": {"title": "Engineer", "created_at": now.isoformat() + "Z"}
        }
        filters = FilterParams(date_from=now - timedelta(hours=1))

        result = apply_filters(content, filters)

        assert len(result) == 1


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_endpoint_available(self):
        """Verify /metrics endpoint exists in router."""
        from app.routers.metrics_router import router

        routes = [route.path for route in router.routes]
        assert "/metrics" in routes


class TestCorrelationMiddleware:
    """Tests for CorrelationIdMiddleware."""

    def test_correlation_id_header_constant(self):
        """Verify correlation ID header constant is correct."""
        assert CORRELATION_ID_HEADER == "X-Correlation-ID"
