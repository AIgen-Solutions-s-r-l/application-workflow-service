"""
Custom exception classes and structured error responses.

This module provides:
- Structured error response format
- Specific exception classes for different error types
- Error codes for programmatic error handling
"""

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.correlation import get_correlation_id


class ErrorCode:
    """Error codes for programmatic error handling."""

    # General errors (1xxx)
    INTERNAL_ERROR = "ERR_1000"
    VALIDATION_ERROR = "ERR_1001"
    NOT_FOUND = "ERR_1002"
    UNAUTHORIZED = "ERR_1003"
    FORBIDDEN = "ERR_1004"

    # Application errors (2xxx)
    APPLICATION_NOT_FOUND = "ERR_2001"
    APPLICATION_INVALID_STATUS = "ERR_2002"
    APPLICATION_ALREADY_PROCESSED = "ERR_2003"
    APPLICATION_SUBMISSION_FAILED = "ERR_2004"

    # Job errors (3xxx)
    JOB_NOT_FOUND = "ERR_3001"
    JOB_INVALID_DATA = "ERR_3002"

    # Resume errors (4xxx)
    RESUME_NOT_FOUND = "ERR_4001"
    RESUME_INVALID_FORMAT = "ERR_4002"
    RESUME_UPLOAD_FAILED = "ERR_4003"

    # Database errors (5xxx)
    DATABASE_ERROR = "ERR_5001"
    DATABASE_CONNECTION_ERROR = "ERR_5002"
    DATABASE_TIMEOUT = "ERR_5003"

    # Queue errors (6xxx)
    QUEUE_ERROR = "ERR_6001"
    QUEUE_CONNECTION_ERROR = "ERR_6002"
    QUEUE_PUBLISH_FAILED = "ERR_6003"

    # Rate limit errors (7xxx)
    RATE_LIMIT_EXCEEDED = "ERR_7001"

    # Authentication errors (8xxx)
    AUTH_TOKEN_INVALID = "ERR_8001"
    AUTH_TOKEN_EXPIRED = "ERR_8002"
    AUTH_INSUFFICIENT_PERMISSIONS = "ERR_8003"

    # Idempotency errors (9xxx)
    DUPLICATE_REQUEST = "ERR_9001"


class ErrorDetail(BaseModel):
    """Structured error detail for API responses."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Structured error response for API."""

    error: str  # Error class name
    code: str  # Error code for programmatic handling
    message: str  # Human-readable message
    details: list[ErrorDetail] | None = None  # Additional error details
    correlation_id: str | None = None  # Request correlation ID
    timestamp: str  # ISO 8601 timestamp
    path: str | None = None  # Request path

    @classmethod
    def create(
        cls,
        error: str,
        code: str,
        message: str,
        details: list[ErrorDetail] | None = None,
        path: str | None = None,
    ) -> "ErrorResponse":
        """Create an error response with current timestamp and correlation ID."""
        return cls(
            error=error,
            code=code,
            message=message,
            details=details,
            correlation_id=get_correlation_id(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            path=path,
        )


class ApplicationManagerException(HTTPException):
    """Base exception for all application manager errors."""

    error_code: str = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: str | None = None,
        details: list[ErrorDetail] | None = None,
    ):
        self.error_code = error_code or self.__class__.error_code
        error_response = ErrorResponse.create(
            error=self.__class__.__name__, code=self.error_code, message=detail, details=details
        )
        super().__init__(status_code=status_code, detail=error_response.model_dump())


# =============================================================================
# Not Found Errors
# =============================================================================


class NotFoundError(ApplicationManagerException):
    """Base class for not found errors."""

    error_code = ErrorCode.NOT_FOUND

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            detail=f"{resource} not found: {identifier}", status_code=status.HTTP_404_NOT_FOUND
        )


class ApplicationNotFoundError(NotFoundError):
    """Raised when an application is not found."""

    error_code = ErrorCode.APPLICATION_NOT_FOUND

    def __init__(self, application_id: str):
        super().__init__(resource="Application", identifier=application_id)


class ResumeNotFoundError(NotFoundError):
    """Raised when a resume is not found in the database."""

    error_code = ErrorCode.RESUME_NOT_FOUND

    def __init__(self, user_id: Any):
        super().__init__(resource="Resume", identifier=f"user_id={user_id}")


class JobNotFoundError(NotFoundError):
    """Raised when a job is not found."""

    error_code = ErrorCode.JOB_NOT_FOUND

    def __init__(self, job_id: str):
        super().__init__(resource="Job", identifier=job_id)


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(ApplicationManagerException):
    """Raised when request validation fails."""

    error_code = ErrorCode.VALIDATION_ERROR

    def __init__(self, message: str, details: list[ErrorDetail] | None = None):
        super().__init__(
            detail=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details
        )


class InvalidResumeFormatError(ValidationError):
    """Raised when resume format is invalid."""

    error_code = ErrorCode.RESUME_INVALID_FORMAT

    def __init__(self, expected_format: str = "PDF"):
        super().__init__(message=f"Invalid resume format. Expected: {expected_format}")


class InvalidJobDataError(ValidationError):
    """Raised when job data is invalid."""

    error_code = ErrorCode.JOB_INVALID_DATA

    def __init__(self, message: str, field: str | None = None):
        details = (
            [ErrorDetail(code=self.error_code, message=message, field=field)] if field else None
        )
        super().__init__(message=message, details=details)


# =============================================================================
# Application State Errors
# =============================================================================


class ApplicationStateError(ApplicationManagerException):
    """Base class for application state errors."""

    error_code = ErrorCode.APPLICATION_INVALID_STATUS

    def __init__(self, message: str):
        super().__init__(detail=message, status_code=status.HTTP_409_CONFLICT)


class ApplicationAlreadyProcessedError(ApplicationStateError):
    """Raised when trying to modify an already processed application."""

    error_code = ErrorCode.APPLICATION_ALREADY_PROCESSED

    def __init__(self, application_id: str, current_status: str):
        super().__init__(
            message=f"Application {application_id} is already {current_status} and cannot be modified"
        )


# =============================================================================
# Operation Errors
# =============================================================================


class JobApplicationError(ApplicationManagerException):
    """Raised when there is an error in the job application process."""

    error_code = ErrorCode.APPLICATION_SUBMISSION_FAILED

    def __init__(self, detail: str):
        super().__init__(
            detail=f"Job application error: {detail}", status_code=status.HTTP_400_BAD_REQUEST
        )


class DatabaseOperationError(ApplicationManagerException):
    """Raised when a database operation fails."""

    error_code = ErrorCode.DATABASE_ERROR

    def __init__(self, detail: str):
        super().__init__(
            detail=f"Database operation failed: {detail}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class DatabaseConnectionError(DatabaseOperationError):
    """Raised when database connection fails."""

    error_code = ErrorCode.DATABASE_CONNECTION_ERROR

    def __init__(self):
        super().__init__(detail="Unable to connect to database")


class QueueOperationError(ApplicationManagerException):
    """Raised when a queue operation fails."""

    error_code = ErrorCode.QUEUE_ERROR

    def __init__(self, detail: str):
        super().__init__(
            detail=f"Queue operation failed: {detail}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class QueuePublishError(QueueOperationError):
    """Raised when publishing to queue fails."""

    error_code = ErrorCode.QUEUE_PUBLISH_FAILED

    def __init__(self, queue_name: str):
        super().__init__(detail=f"Failed to publish message to queue: {queue_name}")


# =============================================================================
# Rate Limiting Errors
# =============================================================================


class RateLimitError(ApplicationManagerException):
    """Raised when rate limit is exceeded."""

    error_code = ErrorCode.RATE_LIMIT_EXCEEDED

    def __init__(self, retry_after: int):
        super().__init__(
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


# =============================================================================
# Authentication Errors
# =============================================================================


class AuthenticationError(ApplicationManagerException):
    """Base class for authentication errors."""

    error_code = ErrorCode.AUTH_TOKEN_INVALID

    def __init__(self, message: str):
        super().__init__(detail=message, status_code=status.HTTP_401_UNAUTHORIZED)


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""

    error_code = ErrorCode.AUTH_TOKEN_EXPIRED

    def __init__(self):
        super().__init__(message="Token has expired")


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""

    error_code = ErrorCode.AUTH_TOKEN_INVALID

    def __init__(self):
        super().__init__(message="Invalid authentication token")


class InsufficientPermissionsError(ApplicationManagerException):
    """Raised when user doesn't have required permissions."""

    error_code = ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS

    def __init__(self, required_permission: str | None = None):
        message = "Insufficient permissions"
        if required_permission:
            message += f": requires {required_permission}"
        super().__init__(detail=message, status_code=status.HTTP_403_FORBIDDEN)


# =============================================================================
# Idempotency Errors
# =============================================================================


class DuplicateRequestError(ApplicationManagerException):
    """Raised when a duplicate request is detected."""

    error_code = ErrorCode.DUPLICATE_REQUEST

    def __init__(self, idempotency_key: str, existing_result: dict | None = None):
        self.existing_result = existing_result
        super().__init__(
            detail=f"Duplicate request detected for idempotency key: {idempotency_key}",
            status_code=status.HTTP_409_CONFLICT,
        )
