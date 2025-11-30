"""
Health check load test tasks.
"""

from locust import HttpUser


class HealthTasks:
    """Tasks for health check endpoints."""

    @classmethod
    def check_health(cls, client: HttpUser) -> dict | None:
        """
        Check full health status.

        Args:
            client: Locust HTTP client.

        Returns:
            Response data if successful, None otherwise.
        """
        with client.get(
            "/health",
            name="GET /health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def check_liveness(cls, client: HttpUser) -> dict | None:
        """
        Check liveness probe.

        Args:
            client: Locust HTTP client.

        Returns:
            Response data if successful, None otherwise.
        """
        with client.get(
            "/health/live",
            name="GET /health/live",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def check_readiness(cls, client: HttpUser) -> dict | None:
        """
        Check readiness probe.

        Args:
            client: Locust HTTP client.

        Returns:
            Response data if successful, None otherwise.
        """
        with client.get(
            "/health/ready",
            name="GET /health/ready",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 503:
                # Service unavailable is a valid response for readiness
                response.success()
                return response.json()
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def get_metrics(cls, client: HttpUser) -> str | None:
        """
        Get Prometheus metrics.

        Args:
            client: Locust HTTP client.

        Returns:
            Metrics text if successful, None otherwise.
        """
        with client.get(
            "/metrics",
            name="GET /metrics",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.text
            else:
                response.failure(f"Status {response.status_code}")
                return None
