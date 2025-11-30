"""Tests for CLI HTTP client."""

from unittest.mock import MagicMock, patch

import pytest

from app.cli.client import APIClient, APIError


class TestAPIError:
    """Tests for APIError exception."""

    def test_api_error_message(self):
        """Test APIError message formatting."""
        error = APIError(404, "Not found")
        assert str(error) == "[404] Not found"
        assert error.status_code == 404
        assert error.message == "Not found"

    def test_api_error_with_details(self):
        """Test APIError with details."""
        error = APIError(400, "Bad request", {"field": "invalid"})
        assert error.details == {"field": "invalid"}


class TestAPIClient:
    """Tests for APIClient class."""

    def test_client_default_config(self):
        """Test client with default configuration."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token=None,
                api_timeout=30,
            )
            client = APIClient()
            assert client.base_url == "http://localhost:8009"
            assert client.token is None
            assert client.timeout == 30

    def test_client_custom_config(self):
        """Test client with custom configuration."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://default:8009",
                api_token="default-token",
                api_timeout=30,
            )
            client = APIClient(
                base_url="http://custom:9000",
                token="custom-token",
                timeout=60,
            )
            assert client.base_url == "http://custom:9000"
            assert client.token == "custom-token"
            assert client.timeout == 60

    def test_get_headers_without_token(self):
        """Test headers without authentication token."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token=None,
                api_timeout=30,
            )
            client = APIClient()
            headers = client._get_headers()
            assert "Authorization" not in headers
            assert headers["Content-Type"] == "application/json"

    def test_get_headers_with_token(self):
        """Test headers with authentication token."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token="test-token",
                api_timeout=30,
            )
            client = APIClient()
            headers = client._get_headers()
            assert headers["Authorization"] == "Bearer test-token"

    def test_handle_response_success(self):
        """Test handling successful response."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token=None,
                api_timeout=30,
            )
            client = APIClient()
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"status": "ok"}

            result = client._handle_response(response)
            assert result == {"status": "ok"}

    def test_handle_response_204(self):
        """Test handling 204 No Content response."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token=None,
                api_timeout=30,
            )
            client = APIClient()
            response = MagicMock()
            response.status_code = 204

            result = client._handle_response(response)
            assert result == {}

    def test_handle_response_error_json(self):
        """Test handling error response with JSON body."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token=None,
                api_timeout=30,
            )
            client = APIClient()
            response = MagicMock()
            response.status_code = 404
            response.json.return_value = {"message": "Not found", "code": "ERR_404"}

            with pytest.raises(APIError) as exc_info:
                client._handle_response(response)

            assert exc_info.value.status_code == 404
            assert exc_info.value.message == "Not found"

    def test_handle_response_error_text(self):
        """Test handling error response with text body."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token=None,
                api_timeout=30,
            )
            client = APIClient()
            response = MagicMock()
            response.status_code = 500
            response.json.side_effect = ValueError()
            response.text = "Internal Server Error"

            with pytest.raises(APIError) as exc_info:
                client._handle_response(response)

            assert exc_info.value.status_code == 500
            assert exc_info.value.message == "Internal Server Error"


class TestAPIClientMethods:
    """Tests for API client convenience methods."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        with patch("app.cli.client.get_config") as mock_config:
            mock_config.return_value = MagicMock(
                api_url="http://localhost:8009",
                api_token="test-token",
                api_timeout=30,
            )
            return APIClient()

    def test_health_endpoint(self, client):
        """Test health endpoint call."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {"status": "healthy"}
            result = client.health()
            mock_get.assert_called_once_with("/health")
            assert result == {"status": "healthy"}

    def test_health_live_endpoint(self, client):
        """Test health live endpoint call."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {"status": "alive"}
            result = client.health_live()
            mock_get.assert_called_once_with("/health/live")
            assert result == {"status": "alive"}

    def test_get_application_status(self, client):
        """Test get application status endpoint."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {"status": "processing"}
            result = client.get_application_status("app123")
            mock_get.assert_called_once_with("/applications/app123/status")
            assert result == {"status": "processing"}

    def test_get_successful_applications(self, client):
        """Test get successful applications with filters."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {"data": {}}
            client.get_successful_applications(
                limit=10,
                portal="LinkedIn",
                company_name="Test",
            )
            mock_get.assert_called_once_with(
                "/applied",
                params={
                    "limit": 10,
                    "portal": "LinkedIn",
                    "company_name": "Test",
                },
            )

    def test_get_failed_applications(self, client):
        """Test get failed applications."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {"data": {}}
            client.get_failed_applications(limit=5)
            mock_get.assert_called_once_with(
                "/fail_applied",
                params={"limit": 5},
            )
