"""
Tests for Sprint 4 features:
- Story #20: Enhanced health checks with dependency status
- Story #21: Specific exception classes and structured error responses
- Story #22: SLO dashboards and alerting (configuration only)
- Story #23: Idempotency keys for duplicate prevention
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import (
    ErrorCode,
    ErrorResponse,
    ErrorDetail,
    ApplicationManagerException,
    ApplicationNotFoundError,
    ResumeNotFoundError,
    JobNotFoundError,
    ValidationError,
    InvalidResumeFormatError,
    InvalidJobDataError,
    ApplicationAlreadyProcessedError,
    DatabaseOperationError,
    DatabaseConnectionError,
    QueueOperationError,
    QueuePublishError,
    RateLimitError,
    AuthenticationError,
    TokenExpiredError,
    InvalidTokenError,
    InsufficientPermissionsError,
    DuplicateRequestError
)
from app.core.idempotency import (
    InMemoryIdempotencyStore,
    IdempotencyRecord,
    generate_request_fingerprint,
    get_idempotency_store,
    IDEMPOTENCY_KEY_HEADER
)
from app.routers.healthcheck_router import (
    DependencyStatus,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse
)


class TestErrorCodes:
    """Tests for Story #21: Error codes."""

    def test_error_codes_are_unique(self):
        """Verify all error codes are unique."""
        codes = [
            getattr(ErrorCode, attr) for attr in dir(ErrorCode)
            if not attr.startswith('_')
        ]
        assert len(codes) == len(set(codes)), "Error codes must be unique"

    def test_error_code_format(self):
        """Verify error codes follow ERR_XXXX format."""
        codes = [
            getattr(ErrorCode, attr) for attr in dir(ErrorCode)
            if not attr.startswith('_')
        ]
        for code in codes:
            assert code.startswith("ERR_"), f"Code {code} should start with ERR_"
            assert len(code) == 8, f"Code {code} should be 8 characters"


class TestErrorResponse:
    """Tests for Story #21: Structured error responses."""

    def test_error_response_creation(self):
        """Verify ErrorResponse can be created."""
        response = ErrorResponse(
            error="TestError",
            code="ERR_1000",
            message="Test error message",
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        assert response.error == "TestError"
        assert response.code == "ERR_1000"
        assert response.message == "Test error message"

    def test_error_response_create_classmethod(self):
        """Verify ErrorResponse.create sets timestamp."""
        response = ErrorResponse.create(
            error="TestError",
            code="ERR_1000",
            message="Test message"
        )

        assert response.timestamp.endswith("Z")
        assert "T" in response.timestamp

    def test_error_response_with_details(self):
        """Verify ErrorResponse can include details."""
        details = [
            ErrorDetail(code="ERR_3002", message="Invalid field", field="title")
        ]
        response = ErrorResponse.create(
            error="ValidationError",
            code="ERR_1001",
            message="Validation failed",
            details=details
        )

        assert len(response.details) == 1
        assert response.details[0].field == "title"


class TestExceptionClasses:
    """Tests for Story #21: Exception classes."""

    def test_application_not_found_error(self):
        """Verify ApplicationNotFoundError structure."""
        with pytest.raises(ApplicationNotFoundError) as exc_info:
            raise ApplicationNotFoundError("app_123")

        assert exc_info.value.status_code == 404
        assert "app_123" in str(exc_info.value.detail)

    def test_resume_not_found_error(self):
        """Verify ResumeNotFoundError structure."""
        with pytest.raises(ResumeNotFoundError) as exc_info:
            raise ResumeNotFoundError("user_456")

        assert exc_info.value.status_code == 404

    def test_job_not_found_error(self):
        """Verify JobNotFoundError structure."""
        with pytest.raises(JobNotFoundError) as exc_info:
            raise JobNotFoundError("job_789")

        assert exc_info.value.status_code == 404

    def test_validation_error(self):
        """Verify ValidationError structure."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Invalid input")

        assert exc_info.value.status_code == 422

    def test_invalid_resume_format_error(self):
        """Verify InvalidResumeFormatError structure."""
        with pytest.raises(InvalidResumeFormatError) as exc_info:
            raise InvalidResumeFormatError("PDF")

        assert exc_info.value.status_code == 422
        assert "PDF" in str(exc_info.value.detail)

    def test_invalid_job_data_error_with_field(self):
        """Verify InvalidJobDataError includes field info."""
        error = InvalidJobDataError("Title is required", field="title")
        assert error.status_code == 422

    def test_application_already_processed_error(self):
        """Verify ApplicationAlreadyProcessedError structure."""
        with pytest.raises(ApplicationAlreadyProcessedError) as exc_info:
            raise ApplicationAlreadyProcessedError("app_123", "success")

        assert exc_info.value.status_code == 409

    def test_database_operation_error(self):
        """Verify DatabaseOperationError structure."""
        with pytest.raises(DatabaseOperationError) as exc_info:
            raise DatabaseOperationError("Connection failed")

        assert exc_info.value.status_code == 500

    def test_database_connection_error(self):
        """Verify DatabaseConnectionError structure."""
        with pytest.raises(DatabaseConnectionError) as exc_info:
            raise DatabaseConnectionError()

        assert exc_info.value.status_code == 500

    def test_queue_operation_error(self):
        """Verify QueueOperationError structure."""
        with pytest.raises(QueueOperationError) as exc_info:
            raise QueueOperationError("Queue unavailable")

        assert exc_info.value.status_code == 500

    def test_queue_publish_error(self):
        """Verify QueuePublishError structure."""
        with pytest.raises(QueuePublishError) as exc_info:
            raise QueuePublishError("application_processing_queue")

        assert exc_info.value.status_code == 500

    def test_rate_limit_error(self):
        """Verify RateLimitError structure."""
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError(retry_after=60)

        assert exc_info.value.status_code == 429
        assert "60" in str(exc_info.value.detail)

    def test_authentication_error(self):
        """Verify AuthenticationError structure."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError("Invalid credentials")

        assert exc_info.value.status_code == 401

    def test_token_expired_error(self):
        """Verify TokenExpiredError structure."""
        with pytest.raises(TokenExpiredError) as exc_info:
            raise TokenExpiredError()

        assert exc_info.value.status_code == 401

    def test_invalid_token_error(self):
        """Verify InvalidTokenError structure."""
        with pytest.raises(InvalidTokenError) as exc_info:
            raise InvalidTokenError()

        assert exc_info.value.status_code == 401

    def test_insufficient_permissions_error(self):
        """Verify InsufficientPermissionsError structure."""
        with pytest.raises(InsufficientPermissionsError) as exc_info:
            raise InsufficientPermissionsError("admin")

        assert exc_info.value.status_code == 403

    def test_duplicate_request_error(self):
        """Verify DuplicateRequestError structure."""
        existing = {"application_id": "app_123"}
        error = DuplicateRequestError("key_abc", existing_result=existing)

        assert error.status_code == 409
        assert error.existing_result == existing


class TestHealthCheckResponses:
    """Tests for Story #20: Health check response models."""

    def test_dependency_status_model(self):
        """Verify DependencyStatus model structure."""
        status = DependencyStatus(
            name="mongodb",
            status="healthy",
            latency_ms=5.2,
            message=None
        )

        assert status.name == "mongodb"
        assert status.status == "healthy"
        assert status.latency_ms == 5.2

    def test_health_response_model(self):
        """Verify HealthResponse model structure."""
        response = HealthResponse(
            status="healthy",
            environment="development",
            timestamp=datetime.utcnow().isoformat() + "Z",
            dependencies=[
                DependencyStatus(name="mongodb", status="healthy"),
                DependencyStatus(name="rabbitmq", status="healthy")
            ]
        )

        assert response.status == "healthy"
        assert response.service == "application-manager-service"
        assert len(response.dependencies) == 2

    def test_liveness_response_model(self):
        """Verify LivenessResponse model structure."""
        response = LivenessResponse(
            status="alive",
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        assert response.status == "alive"

    def test_readiness_response_model(self):
        """Verify ReadinessResponse model structure."""
        response = ReadinessResponse(
            status="ready",
            timestamp=datetime.utcnow().isoformat() + "Z",
            checks={"mongodb": "ready", "rabbitmq": "ready"}
        )

        assert response.status == "ready"
        assert response.checks["mongodb"] == "ready"


class TestIdempotencyStore:
    """Tests for Story #23: Idempotency key storage."""

    def test_store_set_pending(self):
        """Verify setting a key to pending."""
        store = InMemoryIdempotencyStore()

        result = store.set_pending("test_key_1")
        assert result is True

        record = store.get("test_key_1")
        assert record is not None
        assert record.status == "pending"

    def test_store_set_pending_duplicate(self):
        """Verify duplicate pending key returns False."""
        store = InMemoryIdempotencyStore()

        store.set_pending("test_key_2")
        result = store.set_pending("test_key_2")

        assert result is False

    def test_store_set_completed(self):
        """Verify setting a key to completed."""
        store = InMemoryIdempotencyStore()

        store.set_pending("test_key_3")
        store.set_completed("test_key_3", {"result": "success"}, 200)

        record = store.get("test_key_3")
        assert record.status == "completed"
        assert record.response == {"result": "success"}
        assert record.status_code == 200

    def test_store_set_failed(self):
        """Verify setting a key to failed."""
        store = InMemoryIdempotencyStore()

        store.set_pending("test_key_4")
        store.set_failed("test_key_4", "Processing error")

        record = store.get("test_key_4")
        assert record.status == "failed"
        assert "error" in record.response

    def test_store_delete(self):
        """Verify deleting a key."""
        store = InMemoryIdempotencyStore()

        store.set_pending("test_key_5")
        store.delete("test_key_5")

        record = store.get("test_key_5")
        assert record is None

    def test_store_expiration(self):
        """Verify expired keys are cleaned up."""
        store = InMemoryIdempotencyStore(ttl_seconds=1)

        store.set_pending("test_key_6")

        # Manually set created_at to past
        store._store["test_key_6"].created_at = datetime.utcnow() - timedelta(seconds=10)

        # Force cleanup
        store._last_cleanup = 0
        store._cleanup_interval = 0

        record = store.get("test_key_6")
        assert record is None

    def test_get_nonexistent_key(self):
        """Verify getting a non-existent key returns None."""
        store = InMemoryIdempotencyStore()

        record = store.get("nonexistent_key")
        assert record is None


class TestIdempotencyFunctions:
    """Tests for Story #23: Idempotency helper functions."""

    def test_generate_request_fingerprint(self):
        """Verify request fingerprint generation."""
        fp1 = generate_request_fingerprint("POST", "/applications", b'{"test": "data"}', "user_123")
        fp2 = generate_request_fingerprint("POST", "/applications", b'{"test": "data"}', "user_123")
        fp3 = generate_request_fingerprint("POST", "/applications", b'{"test": "other"}', "user_123")

        assert fp1 == fp2  # Same inputs should produce same fingerprint
        assert fp1 != fp3  # Different body should produce different fingerprint
        assert len(fp1) == 64  # SHA256 hex digest length

    def test_generate_request_fingerprint_without_user(self):
        """Verify fingerprint generation without user ID."""
        fp = generate_request_fingerprint("GET", "/health")
        assert len(fp) == 64

    def test_get_idempotency_store_singleton(self):
        """Verify get_idempotency_store returns global instance."""
        store1 = get_idempotency_store()
        store2 = get_idempotency_store()

        assert store1 is store2

    def test_idempotency_key_header_constant(self):
        """Verify idempotency key header constant."""
        assert IDEMPOTENCY_KEY_HEADER == "X-Idempotency-Key"


class TestIdempotencyRecord:
    """Tests for Story #23: IdempotencyRecord model."""

    def test_idempotency_record_creation(self):
        """Verify IdempotencyRecord model structure."""
        record = IdempotencyRecord(
            key="test_key",
            status="pending",
            created_at=datetime.utcnow()
        )

        assert record.key == "test_key"
        assert record.status == "pending"
        assert record.response is None
        assert record.completed_at is None

    def test_idempotency_record_with_response(self):
        """Verify IdempotencyRecord with response data."""
        record = IdempotencyRecord(
            key="test_key",
            status="completed",
            response={"application_id": "app_123"},
            status_code=201,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )

        assert record.status == "completed"
        assert record.response["application_id"] == "app_123"
        assert record.status_code == 201


class TestHealthCheckRoutes:
    """Tests for Story #20: Health check routes."""

    def test_health_routes_exist(self):
        """Verify health check routes are defined."""
        from app.routers.healthcheck_router import router

        routes = [route.path for route in router.routes]
        assert "/health" in routes
        assert "/health/live" in routes
        assert "/health/ready" in routes
        assert "/healthcheck" in routes  # Legacy

    def test_liveness_probe_response_structure(self):
        """Verify liveness probe returns correct structure."""
        response = LivenessResponse(
            status="alive",
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        assert response.status == "alive"


class TestSLOConfiguration:
    """Tests for Story #22: SLO configuration file."""

    def test_slo_config_file_exists(self):
        """Verify SLO configuration file exists."""
        import os
        config_path = "monitoring/slo-config.yaml"

        # This test verifies the file was created
        assert os.path.exists(config_path), "SLO config file should exist"

    def test_slo_config_is_valid_yaml(self):
        """Verify SLO configuration is valid YAML."""
        import yaml

        with open("monitoring/slo-config.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert "slos" in config
        assert "alerting_rules" in config
        assert "dashboards" in config

    def test_slo_targets_defined(self):
        """Verify SLO targets are defined."""
        import yaml

        with open("monitoring/slo-config.yaml", "r") as f:
            config = yaml.safe_load(f)

        slos = config["slos"]
        assert "availability" in slos
        assert "latency_p95" in slos
        assert "latency_p99" in slos

        # Verify availability target
        assert slos["availability"]["target"] == 99.9
