from fastapi.testclient import TestClient
from app.main import app

def test_root_endpoint():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Application Manager Service is running!"}

def test_router_inclusion():
    # Verify that the application router paths are included
    routes = [route.path for route in app.routes]
    assert "/applications" in routes
    assert "/applied" in routes
    assert "/applied/{app_id}" in routes
    assert "/fail_applied" in routes
    assert "/fail_applied/{app_id}" in routes