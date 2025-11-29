"""
Security headers middleware for HTTP response hardening.

Implements OWASP security headers recommendations to protect against
common web vulnerabilities.
"""
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all HTTP responses.

    Headers included:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Legacy XSS protection (for older browsers)
    - Strict-Transport-Security: Enforces HTTPS
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    - Cache-Control: Prevents caching of sensitive data
    """

    def __init__(self, app, include_hsts: bool = True):
        """
        Initialize the security headers middleware.

        Args:
            app: FastAPI application instance.
            include_hsts: Whether to include HSTS header (disable for local dev).
        """
        super().__init__(app)
        self.include_hsts = include_hsts and settings.environment == "production"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy XSS protection (for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=()"
        )

        # Content Security Policy (adjust based on your needs)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # HSTS (only in production)
        if self.include_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Prevent caching of API responses (adjust for static content)
        if not request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, proxy-revalidate"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for secure CORS handling.

    Provides more granular control over CORS than FastAPI's built-in middleware.
    """

    def __init__(
        self,
        app,
        allowed_origins: list[str] = None,
        allowed_methods: list[str] = None,
        allowed_headers: list[str] = None,
        expose_headers: list[str] = None,
        allow_credentials: bool = False,
        max_age: int = 600
    ):
        """
        Initialize CORS middleware.

        Args:
            app: FastAPI application instance.
            allowed_origins: List of allowed origins (None = same-origin only).
            allowed_methods: List of allowed HTTP methods.
            allowed_headers: List of allowed request headers.
            expose_headers: List of headers to expose to the browser.
            allow_credentials: Whether to allow credentials.
            max_age: Preflight cache duration in seconds.
        """
        super().__init__(app)
        self.allowed_origins = set(allowed_origins or [])
        self.allowed_methods = set(allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        self.allowed_headers = set(allowed_headers or [
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "X-Idempotency-Key",
            "X-Request-ID"
        ])
        self.expose_headers = expose_headers or [
            "X-Correlation-ID",
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if the origin is allowed."""
        if not self.allowed_origins:
            return False
        if "*" in self.allowed_origins:
            return True
        return origin in self.allowed_origins

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle CORS headers."""
        origin = request.headers.get("Origin")

        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response(status_code=204)
            if origin and self._is_origin_allowed(origin):
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
                response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
                response.headers["Access-Control-Max-Age"] = str(self.max_age)
                if self.allow_credentials:
                    response.headers["Access-Control-Allow-Credentials"] = "true"
            return response

        # Handle actual requests
        response = await call_next(request)

        if origin and self._is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"

        return response
