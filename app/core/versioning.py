"""
API versioning middleware and utilities.

Provides:
- Version detection from URL path
- Deprecation headers for older API versions
- Version-specific metrics tracking
"""

import re
from datetime import datetime
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.log.logging import logger


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API version detection and deprecation handling.

    Extracts API version from URL path and:
    - Sets version in request state for downstream use
    - Adds deprecation headers for deprecated versions
    - Tracks version usage metrics
    """

    # Pattern to match version prefix in URL
    VERSION_PATTERN = re.compile(r"^/v(\d+)/")

    # Paths excluded from versioning (health checks, metrics, etc.)
    EXCLUDED_PATHS = {"/health", "/health/live", "/health/ready", "/metrics", "/", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add version information.

        Args:
            request: Incoming request.
            call_next: Next middleware/handler.

        Returns:
            Response with version headers.
        """
        path = request.url.path

        # Skip versioning for excluded paths
        if self._is_excluded_path(path):
            return await call_next(request)

        # Extract version from path
        version = self._extract_version(path)
        request.state.api_version = version

        # Log version usage
        logger.debug(
            "API request",
            event_type="api_request",
            version=version,
            path=path,
            method=request.method,
        )

        # Track version metrics
        self._track_version_metrics(version, path, request.method)

        # Process request
        response = await call_next(request)

        # Add version headers
        response.headers["X-API-Version"] = version

        # Add deprecation headers for deprecated versions
        if self._is_deprecated(version):
            self._add_deprecation_headers(response, version)

        return response

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from versioning."""
        # Exact match for excluded paths
        if path in self.EXCLUDED_PATHS:
            return True

        # Check prefixes for paths like /health/live, /docs/, etc.
        for excluded in self.EXCLUDED_PATHS:
            if path.startswith(excluded) and excluded != "/":
                return True

        return False

    def _extract_version(self, path: str) -> str:
        """
        Extract API version from URL path.

        Args:
            path: Request URL path.

        Returns:
            Version string (e.g., "v1", "v2") or default version.
        """
        match = self.VERSION_PATTERN.match(path)
        if match:
            return f"v{match.group(1)}"

        # Return default version for unversioned paths
        return settings.api_default_version

    def _is_deprecated(self, version: str) -> bool:
        """
        Check if a version is deprecated.

        Args:
            version: API version string.

        Returns:
            True if version is deprecated.
        """
        deprecated_versions = settings.api_deprecated_versions
        return version in deprecated_versions

    def _add_deprecation_headers(self, response: Response, version: str) -> None:
        """
        Add deprecation-related headers to response.

        Args:
            response: Response to modify.
            version: Deprecated version.
        """
        # Standard deprecation header (RFC 8594)
        response.headers["Deprecation"] = "true"

        # Sunset header with deprecation date
        sunset_date = settings.api_sunset_dates.get(version)
        if sunset_date:
            response.headers["Sunset"] = sunset_date

        # Link to successor version
        successor = self._get_successor_version(version)
        if successor:
            response.headers["Link"] = f'</{successor}/>; rel="successor-version"'

        # Custom deprecation warning
        if settings.api_deprecation_warnings:
            response.headers["X-Deprecation-Warning"] = (
                f"API {version} is deprecated. "
                f"Please migrate to {successor or 'the latest version'}. "
                f"See documentation for migration guide."
            )

    def _get_successor_version(self, version: str) -> str | None:
        """
        Get the successor version for a deprecated version.

        Args:
            version: Current version.

        Returns:
            Successor version string or None.
        """
        supported = settings.api_supported_versions
        try:
            idx = supported.index(version)
            if idx < len(supported) - 1:
                return supported[idx + 1]
        except ValueError:
            pass
        return None

    def _track_version_metrics(self, version: str, path: str, method: str) -> None:
        """
        Track API version usage in metrics.

        Args:
            version: API version.
            path: Request path.
            method: HTTP method.
        """
        try:
            from app.core.metrics import api_version_requests_total

            # Normalize path to endpoint pattern
            endpoint = self._normalize_endpoint(path)
            api_version_requests_total.labels(
                version=version,
                endpoint=endpoint,
                method=method,
            ).inc()
        except Exception:
            # Don't fail request if metrics tracking fails
            pass

    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize path to endpoint pattern for metrics.

        Replaces IDs with placeholders for better aggregation.

        Args:
            path: Request path.

        Returns:
            Normalized endpoint pattern.
        """
        # Remove version prefix
        path = self.VERSION_PATTERN.sub("/", path)

        # Replace UUIDs with placeholder
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{id}",
            path,
            flags=re.IGNORECASE,
        )

        # Replace MongoDB ObjectIds with placeholder
        path = re.sub(r"/[0-9a-f]{24}", "/{id}", path, flags=re.IGNORECASE)

        # Replace generic IDs (alphanumeric, common patterns)
        path = re.sub(r"/[a-zA-Z0-9_-]{20,}", "/{id}", path)

        return path


def get_api_version(request: Request) -> str:
    """
    Get the API version for the current request.

    Args:
        request: FastAPI request object.

    Returns:
        API version string.
    """
    return getattr(request.state, "api_version", settings.api_default_version)
