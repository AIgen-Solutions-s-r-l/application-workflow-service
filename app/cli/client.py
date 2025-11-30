"""HTTP client for CLI commands."""

import asyncio
from typing import Any

import httpx

from app.cli.config import get_config


class APIError(Exception):
    """API request error."""

    def __init__(self, status_code: int, message: str, details: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{status_code}] {message}")


class APIClient:
    """HTTP client for Application Manager API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: int | None = None,
    ):
        config = get_config()
        self.base_url = (base_url or config.api_url).rstrip("/")
        self.token = token or config.api_token
        self.timeout = timeout or config.api_timeout

    def _get_headers(self) -> dict[str, str]:
        """Get request headers including authorization."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and raise errors if needed."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("message", error_data.get("detail", "Unknown error"))
                raise APIError(response.status_code, message, error_data)
            except ValueError:
                raise APIError(response.status_code, response.text)

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Make an async HTTP request."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                url,
                headers=self._get_headers(),
                params=params,
                json=json,
                **kwargs,
            )
            return self._handle_response(response)

    def request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Make a synchronous HTTP request (runs async internally)."""
        return asyncio.run(self._request(method, path, params, json, **kwargs))

    # Convenience methods
    def get(self, path: str, params: dict | None = None, **kwargs) -> dict[str, Any]:
        """Make a GET request."""
        return self.request("GET", path, params=params, **kwargs)

    def post(
        self, path: str, json: dict | None = None, params: dict | None = None, **kwargs
    ) -> dict[str, Any]:
        """Make a POST request."""
        return self.request("POST", path, params=params, json=json, **kwargs)

    def put(
        self, path: str, json: dict | None = None, params: dict | None = None, **kwargs
    ) -> dict[str, Any]:
        """Make a PUT request."""
        return self.request("PUT", path, params=params, json=json, **kwargs)

    def delete(self, path: str, params: dict | None = None, **kwargs) -> dict[str, Any]:
        """Make a DELETE request."""
        return self.request("DELETE", path, params=params, **kwargs)

    # API-specific methods
    def health(self) -> dict[str, Any]:
        """Get full health status."""
        return self.get("/health")

    def health_live(self) -> dict[str, Any]:
        """Get liveness status."""
        return self.get("/health/live")

    def health_ready(self) -> dict[str, Any]:
        """Get readiness status."""
        return self.get("/health/ready")

    def get_metrics(self) -> str:
        """Get Prometheus metrics."""
        url = f"{self.base_url}/metrics"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self._get_headers())
            if response.status_code >= 400:
                raise APIError(response.status_code, response.text)
            return response.text

    def get_application_status(self, app_id: str) -> dict[str, Any]:
        """Get application status."""
        return self.get(f"/applications/{app_id}/status")

    def get_successful_applications(
        self,
        limit: int = 20,
        cursor: str | None = None,
        portal: str | None = None,
        company_name: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Get successful applications with pagination."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if portal:
            params["portal"] = portal
        if company_name:
            params["company_name"] = company_name
        if title:
            params["title"] = title
        return self.get("/applied", params=params)

    def get_failed_applications(
        self,
        limit: int = 20,
        cursor: str | None = None,
        portal: str | None = None,
    ) -> dict[str, Any]:
        """Get failed applications with pagination."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if portal:
            params["portal"] = portal
        return self.get("/fail_applied", params=params)

    def get_application_details(self, app_id: str, failed: bool = False) -> dict[str, Any]:
        """Get application details."""
        path = f"/fail_applied/{app_id}" if failed else f"/applied/{app_id}"
        return self.get(path)


# Global client instance
_client: APIClient | None = None


def get_client() -> APIClient:
    """Get the global API client."""
    global _client
    if _client is None:
        _client = APIClient()
    return _client


def reset_client() -> None:
    """Reset the global client (useful for testing)."""
    global _client
    _client = None
