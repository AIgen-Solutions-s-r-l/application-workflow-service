"""
Correlation ID middleware for request tracing.

This module provides correlation IDs that propagate through:
- HTTP requests/responses
- Log entries
- Queue messages
- Database operations
"""

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.log.logging import logger

# Context variable to store correlation ID for the current request
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Header names for correlation ID
CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def get_correlation_id() -> str | None:
    """
    Get the current correlation ID.

    Returns:
        The correlation ID for the current context, or None if not set.
    """
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set.
    """
    correlation_id_var.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle correlation IDs for request tracing.

    Features:
    - Extracts correlation ID from incoming request headers
    - Generates new ID if none provided
    - Adds correlation ID to response headers
    - Sets correlation ID in context for logging and downstream calls
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check for existing correlation ID in request headers
        correlation_id = request.headers.get(CORRELATION_ID_HEADER)

        # Generate new ID if not provided
        if not correlation_id:
            correlation_id = generate_correlation_id()

        # Set in context for use throughout the request
        set_correlation_id(correlation_id)

        # Store in request state for easy access in route handlers
        request.state.correlation_id = correlation_id

        # Log the start of the request with correlation ID
        logger.info(
            "Request started",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            event_type="request_start",
        )

        try:
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            response.headers[REQUEST_ID_HEADER] = correlation_id

            # Log the end of the request
            logger.info(
                "Request completed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                event_type="request_complete",
            )

            return response

        except Exception as e:
            # Log the error with correlation ID
            logger.error(
                "Request failed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                event_type="request_error",
            )
            raise


def get_correlation_headers() -> dict:
    """
    Get headers dict with current correlation ID for outgoing requests.

    Use this when making HTTP calls to other services.

    Returns:
        Dictionary with correlation ID header.
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        return {CORRELATION_ID_HEADER: correlation_id}
    return {}


def add_correlation_to_message(message: dict) -> dict:
    """
    Add correlation ID to a message dict for queue publishing.

    Args:
        message: The message dictionary to enrich.

    Returns:
        The message with correlation_id field added.
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        message["correlation_id"] = correlation_id
    return message


def extract_correlation_from_message(message: dict) -> str | None:
    """
    Extract and set correlation ID from a queue message.

    Args:
        message: The message dictionary.

    Returns:
        The correlation ID if found.
    """
    correlation_id = message.get("correlation_id")
    if correlation_id:
        set_correlation_id(correlation_id)
    return correlation_id
