"""
Locust load testing configuration for Application Manager Service.

Usage:
    # Web UI mode
    locust -f load_tests/locustfile.py

    # Headless mode
    locust -f load_tests/locustfile.py --headless -u 100 -r 10 -t 5m

    # With custom host
    locust -f load_tests/locustfile.py --host http://localhost:8009
"""

import random
import sys
from datetime import datetime, timedelta

from locust import HttpUser, between, constant, events, task

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit("/", 1)[0])

from config import AUTH_ALGORITHM, AUTH_SECRET_KEY, BASE_URL, TASK_WEIGHTS, TEST_USER_ID
from tasks.applications import ApplicationTasks
from tasks.health import HealthTasks
from tasks.listing import ListingTasks
from tasks.status import StatusTasks


def generate_jwt_token(user_id: str) -> str:
    """Generate a JWT token for testing."""
    try:
        from jose import jwt

        payload = {
            "id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, AUTH_SECRET_KEY, algorithm=AUTH_ALGORITHM)
    except ImportError:
        # Fallback: return a placeholder token
        # The service should be configured to accept test tokens
        return f"test_token_{user_id}"


class ApplicationManagerUser(HttpUser):
    """
    Standard user behavior for Application Manager Service.

    Simulates typical user activity:
    - Submitting applications (medium frequency)
    - Checking application status (high frequency)
    - Listing applications (medium frequency)
    - Health checks (low frequency)
    """

    host = BASE_URL
    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user with authentication."""
        # Generate unique user ID for this virtual user
        self.user_id = f"{TEST_USER_ID}_{id(self)}"
        self.token = generate_jwt_token(self.user_id)
        self.client.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self.application_ids = []

    @task(TASK_WEIGHTS["submit_application"])
    def submit_application(self):
        """Submit a new application."""
        # Randomly include resume
        with_resume = random.random() < 0.3

        result = ApplicationTasks.submit(self.client, with_resume=with_resume)
        if result and "application_id" in result:
            app_id = result["application_id"]
            self.application_ids.append(app_id)
            StatusTasks.add_application_id(app_id)

    @task(TASK_WEIGHTS["check_status"])
    def check_status(self):
        """Check status of a random application."""
        if self.application_ids:
            app_id = random.choice(self.application_ids)
            StatusTasks.check_status(self.client, app_id)
        else:
            StatusTasks.check_random(self.client)

    @task(TASK_WEIGHTS["list_applications"])
    def list_applications(self):
        """List applications with random filters."""
        if random.random() < 0.5:
            ListingTasks.list_successful(self.client)
        else:
            ListingTasks.list_with_filters(self.client)

    @task(TASK_WEIGHTS["get_application_detail"])
    def get_application_detail(self):
        """Get details for a specific application."""
        if self.application_ids:
            app_id = random.choice(self.application_ids)
            ListingTasks.get_application_detail(self.client, app_id)

    @task(TASK_WEIGHTS["health_check"])
    def health_check(self):
        """Perform a health check."""
        check = random.choice(["health", "live", "ready"])
        if check == "health":
            HealthTasks.check_health(self.client)
        elif check == "live":
            HealthTasks.check_liveness(self.client)
        else:
            HealthTasks.check_readiness(self.client)


class HighFrequencyStatusChecker(HttpUser):
    """
    User that primarily checks status.

    Simulates monitoring dashboards or automated status checkers.
    """

    host = BASE_URL
    wait_time = constant(0.1)  # 10 requests per second per user
    weight = 2  # Lower weight than standard users

    def on_start(self):
        """Initialize user with authentication."""
        self.user_id = f"status_checker_{id(self)}"
        self.token = generate_jwt_token(self.user_id)
        self.client.headers = {"Authorization": f"Bearer {self.token}"}

    @task(10)
    def check_status(self):
        """Check application status."""
        StatusTasks.check_random(self.client)

    @task(1)
    def check_health(self):
        """Check service health."""
        HealthTasks.check_liveness(self.client)


class BurstSubmitter(HttpUser):
    """
    User that submits applications in bursts.

    Simulates batch import or automated submission tools.
    """

    host = BASE_URL
    wait_time = between(5, 10)
    weight = 1  # Lowest weight

    def on_start(self):
        """Initialize user with authentication."""
        self.user_id = f"burst_submitter_{id(self)}"
        self.token = generate_jwt_token(self.user_id)
        self.client.headers = {"Authorization": f"Bearer {self.token}"}

    @task
    def burst_submit(self):
        """Submit multiple applications in quick succession."""
        for _ in range(random.randint(3, 10)):
            result = ApplicationTasks.submit(self.client)
            if result and "application_id" in result:
                StatusTasks.add_application_id(result["application_id"])


# Event handlers for custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log request metrics for analysis."""
    if exception:
        print(f"Request failed: {name} - {exception}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when a new load test starts."""
    print(f"Load test starting against {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("Load test completed")
