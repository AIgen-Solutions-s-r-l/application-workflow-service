"""
Listing and pagination load test tasks.
"""

import random

from locust import HttpUser


class ListingTasks:
    """Tasks for listing and pagination endpoints."""

    PORTALS = ["LinkedIn", "Indeed", "Glassdoor", "AngelList", None]
    COMPANIES = ["Google", "Amazon", "Microsoft", "Meta", "Apple", None]
    TITLES = ["Engineer", "Developer", "Manager", "Designer", None]

    @classmethod
    def list_successful(
        cls,
        client: HttpUser,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict | None:
        """
        List successful applications with pagination.

        Args:
            client: Locust HTTP client.
            limit: Number of results per page.
            cursor: Pagination cursor.

        Returns:
            Response data if successful, None otherwise.
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        with client.get(
            "/applied",
            params=params,
            name="GET /applied",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 429:
                response.success()
                return None
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def list_failed(
        cls,
        client: HttpUser,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict | None:
        """
        List failed applications with pagination.

        Args:
            client: Locust HTTP client.
            limit: Number of results per page.
            cursor: Pagination cursor.

        Returns:
            Response data if successful, None otherwise.
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        with client.get(
            "/fail_applied",
            params=params,
            name="GET /fail_applied",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 429:
                response.success()
                return None
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def list_with_filters(cls, client: HttpUser) -> dict | None:
        """
        List applications with random filters.

        Args:
            client: Locust HTTP client.

        Returns:
            Response data if successful, None otherwise.
        """
        params = {"limit": random.randint(10, 50)}

        # Randomly add filters
        if random.random() > 0.5:
            portal = random.choice(cls.PORTALS)
            if portal:
                params["portal"] = portal

        if random.random() > 0.7:
            company = random.choice(cls.COMPANIES)
            if company:
                params["company_name"] = company

        if random.random() > 0.7:
            title = random.choice(cls.TITLES)
            if title:
                params["title"] = title

        with client.get(
            "/applied",
            params=params,
            name="GET /applied (filtered)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 429:
                response.success()
                return None
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def get_application_detail(cls, client: HttpUser, app_id: str) -> dict | None:
        """
        Get detailed information for a specific application.

        Args:
            client: Locust HTTP client.
            app_id: Application ID.

        Returns:
            Response data if successful, None otherwise.
        """
        with client.get(
            f"/applied/{app_id}",
            name="GET /applied/{id}",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 404:
                # Not found is expected for test IDs
                response.success()
                return None
            elif response.status_code == 429:
                response.success()
                return None
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def paginate_all(cls, client: HttpUser, max_pages: int = 5) -> int:
        """
        Paginate through all applications.

        Args:
            client: Locust HTTP client.
            max_pages: Maximum pages to fetch.

        Returns:
            Total number of applications fetched.
        """
        total = 0
        cursor = None

        for _ in range(max_pages):
            result = cls.list_successful(client, limit=50, cursor=cursor)
            if result is None:
                break

            data = result.get("data", {})
            total += len(data)

            pagination = result.get("pagination", {})
            if not pagination.get("has_more"):
                break

            cursor = pagination.get("next_cursor")
            if not cursor:
                break

        return total
