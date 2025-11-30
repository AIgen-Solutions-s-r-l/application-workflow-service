from fastapi.testclient import TestClient
from app.main import app

def test_root_endpoint():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Application Manager Service is running!"
    assert "api_versions" in data
    assert "default_version" in data


def test_router_inclusion():
    # Verify that the application router paths are included
    routes = [route.path for route in app.routes]

    # v1 routes
    assert "/v1/applications" in routes
    assert "/v1/applied" in routes
    assert "/v1/applied/{app_id}" in routes
    assert "/v1/fail_applied" in routes
    assert "/v1/fail_applied/{app_id}" in routes

    # v2 routes
    assert "/v2/applications" in routes
    assert "/v2/applied" in routes

    # Legacy routes (for backward compatibility)
    assert "/applications" in routes
    assert "/applied" in routes
    assert "/fail_applied" in routes