"""
Retry mechanism with exponential backoff for application processing.

This module provides retry logic for handling transient failures during
application processing, with configurable backoff and error classification.
"""
import asyncio
import functools
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.log.logging import logger


class RetryableError(Exception):
    """
    Exception for errors that can be retried.

    Examples: Network timeouts, database connection failures,
    RabbitMQ unavailable, rate limit exceeded.
    """
    pass


class NonRetryableError(Exception):
    """
    Exception for errors that should not be retried.

    Examples: Invalid application data, authentication failures,
    business logic violations, data validation errors.
    """
    pass


class MaxRetriesExceededError(Exception):
    """
    Exception raised when maximum retry attempts are exhausted.
    """
    def __init__(self, message: str, last_error: Exception, attempts: int):
        super().__init__(message)
        self.last_error = last_error
        self.attempts = attempts


def calculate_backoff_delay(attempt: int, base_delay: float = None, max_delay: float = None) -> float:
    """
    Calculate exponential backoff delay for a given attempt.

    Args:
        attempt: Current attempt number (1-indexed).
        base_delay: Base delay in seconds (default from config).
        max_delay: Maximum delay in seconds (default from config).

    Returns:
        Delay in seconds before next retry.
    """
    base = base_delay or settings.retry_base_delay
    maximum = max_delay or settings.retry_max_delay

    # Exponential backoff: base * 2^(attempt-1)
    delay = base * (2 ** (attempt - 1))
    return min(delay, maximum)


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = None,
    retryable_exceptions: tuple[type[Exception], ...] = (RetryableError,),
    on_retry: Callable[[int, Exception], Any] | None = None,
    **kwargs
) -> Any:
    """
    Execute a function with retry and exponential backoff.

    Args:
        func: Async function to execute.
        *args: Arguments to pass to the function.
        max_retries: Maximum number of retry attempts (default from config).
        retryable_exceptions: Tuple of exception types that trigger a retry.
        on_retry: Optional callback called on each retry (attempt, exception).
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        Result of the function if successful.

    Raises:
        NonRetryableError: If a non-retryable error occurs.
        MaxRetriesExceededError: If max retries are exhausted.
    """
    max_attempts = (max_retries or settings.max_retries) + 1  # +1 for initial attempt
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)

        except NonRetryableError:
            # Don't retry non-retryable errors
            raise

        except retryable_exceptions as e:
            last_error = e

            if attempt >= max_attempts:
                logger.error(
                    "Max retries exceeded for function {func_name}",
                    func_name=func.__name__,
                    attempts=attempt,
                    error=str(e),
                    event_type="retry_exhausted"
                )
                raise MaxRetriesExceededError(
                    f"Max retries ({max_attempts}) exceeded: {str(e)}",
                    last_error=e,
                    attempts=attempt
                )

            delay = calculate_backoff_delay(attempt)

            logger.warning(
                "Retrying {func_name} after {delay}s (attempt {attempt}/{max_attempts})",
                func_name=func.__name__,
                delay=delay,
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(e),
                event_type="retry_attempt"
            )

            if on_retry:
                on_retry(attempt, e)

            await asyncio.sleep(delay)

        except Exception as e:
            # Unexpected error - wrap as non-retryable
            logger.error(
                "Unexpected error in {func_name}: {error}",
                func_name=func.__name__,
                error=str(e),
                error_type=type(e).__name__,
                event_type="unexpected_error"
            )
            raise NonRetryableError(f"Unexpected error: {str(e)}") from e

    # Should not reach here, but just in case
    raise MaxRetriesExceededError(
        "Max retries exceeded",
        last_error=last_error,
        attempts=max_attempts
    )


def with_retry(
    max_retries: int = None,
    retryable_exceptions: tuple[type[Exception], ...] = (RetryableError,)
):
    """
    Decorator to add retry logic with exponential backoff to async functions.

    Usage:
        @with_retry(max_retries=3)
        async def my_function():
            ...

    Args:
        max_retries: Maximum number of retry attempts.
        retryable_exceptions: Tuple of exception types that trigger a retry.

    Returns:
        Decorated function with retry logic.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper
    return decorator


class RetryContext:
    """
    Context manager for tracking retry state during processing.

    Usage:
        async with RetryContext(application_id) as ctx:
            ctx.attempt = 1
            # ... processing logic
            if error:
                ctx.record_error(error)
    """

    def __init__(self, application_id: str, max_retries: int = None):
        self.application_id = application_id
        self.max_retries = max_retries or settings.max_retries
        self.attempt = 0
        self.errors = []
        self.started_at = None
        self.completed_at = None

    async def __aenter__(self):
        self.started_at = datetime.utcnow()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.completed_at = datetime.utcnow()
        return False  # Don't suppress exceptions

    def record_error(self, error: Exception):
        """Record an error that occurred during processing."""
        self.errors.append({
            "attempt": self.attempt,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat()
        })

    @property
    def can_retry(self) -> bool:
        """Check if more retries are available."""
        return self.attempt < self.max_retries

    @property
    def next_delay(self) -> float:
        """Get the delay before next retry."""
        return calculate_backoff_delay(self.attempt)

    def to_dict(self) -> dict:
        """Convert context to dictionary for logging/storage."""
        return {
            "application_id": self.application_id,
            "attempt": self.attempt,
            "max_retries": self.max_retries,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
