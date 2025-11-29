"""
Idempotency key handling for duplicate request prevention.

This module provides:
- In-memory idempotency key storage (for single-instance deployments)
- Configurable TTL for stored keys
- Request fingerprinting for automatic deduplication
"""
import hashlib
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

from fastapi import Request
from pydantic import BaseModel

from app.core.correlation import get_correlation_id
from app.core.exceptions import DuplicateRequestError
from app.log.logging import logger

# Header name for idempotency key
IDEMPOTENCY_KEY_HEADER = "X-Idempotency-Key"

# Default TTL for idempotency keys (24 hours)
DEFAULT_TTL_SECONDS = 86400


class IdempotencyRecord(BaseModel):
    """Record of an idempotent request."""
    key: str
    status: str  # "pending", "completed", "failed"
    response: dict[str, Any] | None = None
    status_code: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    correlation_id: str | None = None


class InMemoryIdempotencyStore:
    """
    In-memory idempotency key storage.

    Note: This implementation is suitable for single-instance deployments.
    For distributed deployments, use Redis-based storage.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._store: dict[str, IdempotencyRecord] = {}
        self._ttl_seconds = ttl_seconds
        self._cleanup_interval = 3600  # Cleanup every hour
        self._last_cleanup = time.time()

    def _cleanup_expired(self):
        """Remove expired idempotency records."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = datetime.utcnow() - timedelta(seconds=self._ttl_seconds)
        expired_keys = [
            key for key, record in self._store.items()
            if record.created_at < cutoff
        ]

        for key in expired_keys:
            del self._store[key]

        if expired_keys:
            logger.info(
                "Cleaned up {count} expired idempotency keys",
                count=len(expired_keys),
                event_type="idempotency_cleanup"
            )

        self._last_cleanup = now

    def get(self, key: str) -> IdempotencyRecord | None:
        """
        Get an idempotency record by key.

        Args:
            key: The idempotency key.

        Returns:
            The idempotency record if found and not expired, None otherwise.
        """
        self._cleanup_expired()

        record = self._store.get(key)
        if record is None:
            return None

        # Check if expired
        age = (datetime.utcnow() - record.created_at).total_seconds()
        if age > self._ttl_seconds:
            del self._store[key]
            return None

        return record

    def set_pending(self, key: str) -> bool:
        """
        Mark a key as pending (request in progress).

        Args:
            key: The idempotency key.

        Returns:
            True if successfully set, False if key already exists.
        """
        if self.get(key) is not None:
            return False

        self._store[key] = IdempotencyRecord(
            key=key,
            status="pending",
            created_at=datetime.utcnow(),
            correlation_id=get_correlation_id()
        )

        logger.debug(
            "Idempotency key {key} set to pending",
            key=key,
            event_type="idempotency_pending"
        )

        return True

    def set_completed(
        self,
        key: str,
        response: dict[str, Any],
        status_code: int
    ) -> None:
        """
        Mark a key as completed with response.

        Args:
            key: The idempotency key.
            response: The response to store.
            status_code: The HTTP status code.
        """
        record = self._store.get(key)
        if record is None:
            # Create new record if not exists (shouldn't happen normally)
            record = IdempotencyRecord(
                key=key,
                status="completed",
                response=response,
                status_code=status_code,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                correlation_id=get_correlation_id()
            )
        else:
            record.status = "completed"
            record.response = response
            record.status_code = status_code
            record.completed_at = datetime.utcnow()

        self._store[key] = record

        logger.debug(
            "Idempotency key {key} completed",
            key=key,
            status_code=status_code,
            event_type="idempotency_completed"
        )

    def set_failed(self, key: str, error: str) -> None:
        """
        Mark a key as failed.

        Args:
            key: The idempotency key.
            error: The error message.
        """
        record = self._store.get(key)
        if record:
            record.status = "failed"
            record.response = {"error": error}
            record.completed_at = datetime.utcnow()
            self._store[key] = record

        logger.debug(
            "Idempotency key {key} failed",
            key=key,
            error=error,
            event_type="idempotency_failed"
        )

    def delete(self, key: str) -> None:
        """Delete an idempotency record."""
        if key in self._store:
            del self._store[key]


# Global idempotency store
_idempotency_store = InMemoryIdempotencyStore()


def get_idempotency_store() -> InMemoryIdempotencyStore:
    """Get the global idempotency store."""
    return _idempotency_store


def generate_request_fingerprint(
    method: str,
    path: str,
    body: bytes | None = None,
    user_id: str | None = None
) -> str:
    """
    Generate a fingerprint for a request.

    Args:
        method: HTTP method.
        path: Request path.
        body: Request body bytes.
        user_id: User ID if authenticated.

    Returns:
        SHA256 hash of the request fingerprint.
    """
    fingerprint_parts = [method, path]

    if user_id:
        fingerprint_parts.append(user_id)

    if body:
        fingerprint_parts.append(body.decode('utf-8', errors='ignore'))

    fingerprint = "|".join(fingerprint_parts)
    return hashlib.sha256(fingerprint.encode()).hexdigest()


def get_idempotency_key(request: Request) -> str | None:
    """
    Extract idempotency key from request headers.

    Args:
        request: The FastAPI request.

    Returns:
        The idempotency key if present, None otherwise.
    """
    return request.headers.get(IDEMPOTENCY_KEY_HEADER)


def require_idempotency(func: Callable) -> Callable:
    """
    Decorator to require idempotency key for an endpoint.

    Usage:
        @router.post("/applications")
        @require_idempotency
        async def create_application(request: Request, ...):
            ...
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        idempotency_key = get_idempotency_key(request)

        if idempotency_key is None:
            # No idempotency key, proceed normally
            return await func(request, *args, **kwargs)

        store = get_idempotency_store()
        existing = store.get(idempotency_key)

        if existing is not None:
            if existing.status == "pending":
                # Request is still being processed
                logger.warning(
                    "Duplicate request while processing for key {key}",
                    key=idempotency_key,
                    event_type="idempotency_conflict"
                )
                raise DuplicateRequestError(
                    idempotency_key=idempotency_key,
                    existing_result={"status": "pending"}
                )

            if existing.status == "completed" and existing.response:
                # Return cached response
                logger.info(
                    "Returning cached response for idempotency key {key}",
                    key=idempotency_key,
                    event_type="idempotency_cache_hit"
                )
                return existing.response

            if existing.status == "failed":
                # Previous request failed, allow retry
                store.delete(idempotency_key)

        # Set pending status
        if not store.set_pending(idempotency_key):
            # Race condition - key was set by another request
            raise DuplicateRequestError(
                idempotency_key=idempotency_key,
                existing_result={"status": "pending"}
            )

        try:
            # Execute the actual function
            result = await func(request, *args, **kwargs)

            # Store successful result
            response_dict = result if isinstance(result, dict) else result.model_dump() if hasattr(result, 'model_dump') else {"result": str(result)}
            store.set_completed(idempotency_key, response_dict, 200)

            return result

        except Exception as e:
            # Mark as failed on error
            store.set_failed(idempotency_key, str(e))
            raise

    return wrapper


class IdempotencyMiddleware:
    """
    Middleware for automatic idempotency handling on POST/PUT/PATCH requests.

    Usage:
        app.add_middleware(IdempotencyMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Only apply to mutating methods
        if request.method not in ["POST", "PUT", "PATCH"]:
            await self.app(scope, receive, send)
            return

        idempotency_key = get_idempotency_key(request)

        if idempotency_key is None:
            await self.app(scope, receive, send)
            return

        store = get_idempotency_store()
        existing = store.get(idempotency_key)

        if existing is not None and existing.status == "completed" and existing.response:
            # Return cached response
            logger.info(
                "Returning cached response for idempotency key {key}",
                key=idempotency_key,
                event_type="idempotency_cache_hit"
            )

            from fastapi.responses import JSONResponse
            response = JSONResponse(
                content=existing.response,
                status_code=existing.status_code or 200,
                headers={"X-Idempotency-Replayed": "true"}
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
