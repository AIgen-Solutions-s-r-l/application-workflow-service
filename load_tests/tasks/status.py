"""
Status check load test tasks.
"""

import random

from locust import HttpUser


class StatusTasks:
    """Tasks for application status endpoints."""

    # Store submitted application IDs for status checks
    _application_ids: list[str] = []

    @classmethod
    def add_application_id(cls, app_id: str) -> None:
        """Add an application ID to track."""
        cls._application_ids.append(app_id)
        # Keep list bounded to prevent memory issues
        if len(cls._application_ids) > 10000:
            cls._application_ids = cls._application_ids[-5000:]

    @classmethod
    def get_random_app_id(cls) -> str | None:
        """Get a random tracked application ID."""
        if not cls._application_ids:
            return None
        return random.choice(cls._application_ids)

    @classmethod
    def check_status(cls, client: HttpUser, app_id: str) -> dict | None:
        """
        Check status of a specific application.

        Args:
            client: Locust HTTP client.
            app_id: Application ID to check.

        Returns:
            Response data if successful, None otherwise.
        """
        with client.get(
            f"/applications/{app_id}/status",
            name="GET /applications/{id}/status",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 404:
                # Application not found - this is expected for some test IDs
                response.success()
                return None
            elif response.status_code == 429:
                response.success()
                return None
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def check_random(cls, client: HttpUser) -> dict | None:
        """
        Check status of a random tracked application.

        Args:
            client: Locust HTTP client.

        Returns:
            Response data if successful, None otherwise.
        """
        app_id = cls.get_random_app_id()
        if app_id is None:
            # No applications tracked yet, use a dummy ID
            app_id = "test_app_" + str(random.randint(1, 1000))
        return cls.check_status(client, app_id)

    @classmethod
    def poll_until_complete(
        cls, client: HttpUser, app_id: str, max_polls: int = 10
    ) -> str | None:
        """
        Poll application status until it reaches a terminal state.

        Args:
            client: Locust HTTP client.
            app_id: Application ID to poll.
            max_polls: Maximum number of poll attempts.

        Returns:
            Final status if reached, None if timed out.
        """
        for _ in range(max_polls):
            result = cls.check_status(client, app_id)
            if result is None:
                return None

            status = result.get("status")
            if status in ("success", "failed"):
                return status

        return None
