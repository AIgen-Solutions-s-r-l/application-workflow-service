"""
Rate limiting for API endpoints.

This module provides per-user rate limiting to protect against abuse
while maintaining good UX for legitimate users.
"""
import time
from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.log.logging import logger


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, limit: int, reset_at: datetime, retry_after: int):
        self.limit = limit
        self.reset_at = reset_at
        self.retry_after = retry_after
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_at.timestamp()))
            }
        )


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.

    Note: This implementation is suitable for single-instance deployments.
    For distributed deployments, use Redis-based rate limiting.
    """

    def __init__(self):
        self._windows: dict = {}  # user_id -> [(timestamp, count)]
        self._cleanup_interval = 3600  # Cleanup every hour
        self._last_cleanup = time.time()

    def _parse_limit(self, limit_str: str) -> tuple[int, int]:
        """
        Parse limit string like "100/hour" or "1000/minute".

        Returns:
            Tuple of (max_requests, window_seconds).
        """
        parts = limit_str.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid limit format: {limit_str}")

        count = int(parts[0])
        period = parts[1].lower()

        period_seconds = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }.get(period)

        if period_seconds is None:
            raise ValueError(f"Invalid period: {period}")

        return count, period_seconds

    def _cleanup_old_entries(self):
        """Remove expired entries to prevent memory leaks."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - 86400  # Keep entries for 24 hours max
        for user_id in list(self._windows.keys()):
            self._windows[user_id] = [
                (ts, count) for ts, count in self._windows[user_id]
                if ts > cutoff
            ]
            if not self._windows[user_id]:
                del self._windows[user_id]

        self._last_cleanup = now

    def check_rate_limit(
        self,
        user_id: str,
        limit_str: str,
        increment: int = 1
    ) -> tuple[bool, int, int, datetime]:
        """
        Check if a request is within rate limits.

        Args:
            user_id: Unique identifier for the user.
            limit_str: Limit string like "100/hour".
            increment: Number of requests to add (default 1).

        Returns:
            Tuple of (allowed, remaining, limit, reset_at).
        """
        self._cleanup_old_entries()

        max_requests, window_seconds = self._parse_limit(limit_str)
        now = time.time()
        window_start = now - window_seconds

        # Get or create user's request history
        if user_id not in self._windows:
            self._windows[user_id] = []

        # Filter to current window
        current_window = [
            (ts, count) for ts, count in self._windows[user_id]
            if ts > window_start
        ]

        # Count requests in window
        total_requests = sum(count for _, count in current_window)

        # Calculate remaining
        remaining = max(0, max_requests - total_requests)

        # Calculate reset time
        if current_window:
            oldest_request = min(ts for ts, _ in current_window)
            reset_timestamp = oldest_request + window_seconds
        else:
            reset_timestamp = now + window_seconds

        reset_at = datetime.fromtimestamp(reset_timestamp)

        # Check if within limit
        if total_requests + increment > max_requests:
            return False, remaining, max_requests, reset_at

        # Add request
        current_window.append((now, increment))
        self._windows[user_id] = current_window

        return True, remaining - increment, max_requests, reset_at

    def get_headers(
        self,
        remaining: int,
        limit: int,
        reset_at: datetime
    ) -> dict:
        """
        Get rate limit headers for response.

        Args:
            remaining: Remaining requests in window.
            limit: Maximum requests allowed.
            reset_at: When the window resets.

        Returns:
            Dictionary of rate limit headers.
        """
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_at.timestamp()))
        }


# Global rate limiter instance
_rate_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


def get_user_identifier(request: Request) -> str:
    """
    Extract user identifier from request.

    Uses user ID from JWT if available, otherwise falls back to IP.
    """
    # Try to get user from request state (set by auth middleware)
    if hasattr(request.state, "user_id"):
        return f"user:{request.state.user_id}"

    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


class RateLimitMiddleware:
    """
    Middleware for applying rate limits to all requests.

    Usage:
        app.add_middleware(RateLimitMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/health/live", "/health/ready", "/healthcheck", "/metrics", "/"]:
            await self.app(scope, receive, send)
            return

        user_id = get_user_identifier(request)
        limiter = get_rate_limiter()

        allowed, remaining, limit, reset_at = limiter.check_rate_limit(
            user_id=user_id,
            limit_str=settings.rate_limit_requests
        )

        if not allowed:
            retry_after = int((reset_at - datetime.now()).total_seconds())
            retry_after = max(1, retry_after)

            logger.warning(
                "Rate limit exceeded for {user_id}",
                user_id=user_id,
                path=request.url.path,
                event_type="rate_limit_exceeded"
            )

            response = JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "limit": limit,
                    "reset_at": reset_at.isoformat()
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_at.timestamp()))
                }
            )

            await response(scope, receive, send)
            return

        # Add rate limit headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"x-ratelimit-limit"] = str(limit).encode()
                headers[b"x-ratelimit-remaining"] = str(remaining).encode()
                headers[b"x-ratelimit-reset"] = str(int(reset_at.timestamp())).encode()
                message["headers"] = list(headers.items())
            await send(message)

        await self.app(scope, receive, send_with_headers)


def rate_limit(limit_str: str = None):
    """
    Decorator to apply rate limiting to specific endpoints.

    Usage:
        @router.post("/applications")
        @rate_limit("100/hour")
        async def submit_application(...):
            ...

    Args:
        limit_str: Limit string like "100/hour" (default from config).
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args, **kwargs):
            if not settings.rate_limit_enabled:
                return await func(request, *args, **kwargs)

            user_id = get_user_identifier(request)
            limiter = get_rate_limiter()
            limit = limit_str or settings.rate_limit_applications

            allowed, remaining, max_limit, reset_at = limiter.check_rate_limit(
                user_id=user_id,
                limit_str=limit
            )

            if not allowed:
                retry_after = int((reset_at - datetime.now()).total_seconds())
                retry_after = max(1, retry_after)

                logger.warning(
                    "Rate limit exceeded for {user_id} on {endpoint}",
                    user_id=user_id,
                    endpoint=func.__name__,
                    event_type="rate_limit_exceeded"
                )

                raise RateLimitExceeded(
                    limit=max_limit,
                    reset_at=reset_at,
                    retry_after=retry_after
                )

            # Store headers for response
            request.state.rate_limit_headers = limiter.get_headers(
                remaining, max_limit, reset_at
            )

            return await func(request, *args, **kwargs)

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
