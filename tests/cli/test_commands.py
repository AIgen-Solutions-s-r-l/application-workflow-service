"""Tests for CLI commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


class TestHealthCommand:
    """Tests for health command."""

    def test_health_command_success(self):
        """Test successful health check."""
        mock_data = {
            "status": "healthy",
            "timestamp": "2025-01-01T00:00:00Z",
            "dependencies": {
                "mongodb": "ready",
                "rabbitmq": "ready",
            },
        }

        with patch("app.cli.commands.health.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.health.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["health"])
            assert result.exit_code == 0
            assert "healthy" in result.stdout.lower() or "Health Status" in result.stdout

    def test_health_command_live(self):
        """Test liveness check."""
        mock_data = {"status": "alive", "timestamp": "2025-01-01T00:00:00Z"}

        with patch("app.cli.commands.health.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.health_live.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["health", "--live"])
            assert result.exit_code == 0

    def test_health_command_ready(self):
        """Test readiness check."""
        mock_data = {"status": "ready", "checks": {"mongodb": "ready"}}

        with patch("app.cli.commands.health.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.health_ready.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["health", "--ready"])
            assert result.exit_code == 0

    def test_health_command_unhealthy(self):
        """Test unhealthy status returns exit code 1."""
        mock_data = {"status": "unhealthy"}

        with patch("app.cli.commands.health.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.health.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["health"])
            assert result.exit_code == 1


class TestAppsCommand:
    """Tests for apps commands."""

    def test_apps_list(self):
        """Test listing applications."""
        mock_data = {
            "data": {
                "app1": {
                    "title": "Software Engineer",
                    "company_name": "Test Corp",
                    "portal": "LinkedIn",
                    "status": "success",
                }
            },
            "pagination": {"total_count": 1, "has_more": False},
        }

        with patch("app.cli.commands.apps.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_successful_applications.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["apps", "list"])
            assert result.exit_code == 0

    def test_apps_list_failed(self):
        """Test listing failed applications."""
        mock_data = {"data": {}, "pagination": {"total_count": 0}}

        with patch("app.cli.commands.apps.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_failed_applications.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["apps", "list", "--failed"])
            assert result.exit_code == 0
            mock_client.get_failed_applications.assert_called_once()

    def test_apps_get(self):
        """Test getting application details."""
        mock_data = {
            "id": "app123",
            "title": "Software Engineer",
            "status": "success",
        }

        with patch("app.cli.commands.apps.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_application_details.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["apps", "get", "app123"])
            assert result.exit_code == 0

    def test_apps_status(self):
        """Test getting application status."""
        mock_data = {"application_id": "app123", "status": "processing"}

        with patch("app.cli.commands.apps.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_application_status.return_value = mock_data
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["apps", "status", "app123"])
            assert result.exit_code == 0


class TestMetricsCommand:
    """Tests for metrics command."""

    def test_metrics_summary(self):
        """Test metrics summary output."""
        mock_metrics = """
# HELP http_requests_total Total HTTP requests
http_requests_total{method="GET"} 100
# HELP applications_submitted_total Total applications
applications_submitted_total 50
"""

        with patch("app.cli.commands.metrics.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_metrics.return_value = mock_metrics
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["metrics"])
            assert result.exit_code == 0

    def test_metrics_raw(self):
        """Test raw metrics output."""
        mock_metrics = "http_requests_total 100\n"

        with patch("app.cli.commands.metrics.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_metrics.return_value = mock_metrics
            mock_get_client.return_value = mock_client

            result = runner.invoke(app, ["metrics", "--raw"])
            assert result.exit_code == 0
            assert "http_requests_total" in result.stdout


class TestConfigCommand:
    """Tests for config commands."""

    def test_config_show(self):
        """Test showing configuration."""
        with patch("app.cli.commands.config.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.api_url = "http://localhost:8009"
            mock_config.api_token = None
            mock_config.api_timeout = 30
            mock_config.output_format = "table"
            mock_config.no_color = False
            mock_get_config.return_value = mock_config

            with patch("app.cli.commands.config.get_config_file") as mock_file:
                mock_file.return_value = MagicMock(exists=lambda: False)

                result = runner.invoke(app, ["config", "show"])
                assert result.exit_code == 0
                assert "localhost:8009" in result.stdout

    def test_config_set_url(self, tmp_path):
        """Test setting configuration value."""
        config_file = tmp_path / "config.env"

        with patch("app.cli.config.get_config_file", return_value=config_file):
            result = runner.invoke(app, ["config", "set", "url", "http://test:9000"])
            assert result.exit_code == 0

    def test_config_set_invalid_key(self):
        """Test setting invalid configuration key."""
        result = runner.invoke(app, ["config", "set", "invalid", "value"])
        assert result.exit_code == 1
        assert "Unknown" in result.stdout


class TestVersionFlag:
    """Tests for version flag."""

    def test_version_flag(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.stdout


class TestHelpOutput:
    """Tests for help output."""

    def test_main_help(self):
        """Test main help output."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "health" in result.stdout
        assert "apps" in result.stdout
        assert "queue" in result.stdout
        assert "export" in result.stdout
        assert "metrics" in result.stdout
        assert "config" in result.stdout

    def test_health_help(self):
        """Test health command help."""
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
        assert "--live" in result.stdout
        assert "--ready" in result.stdout

    def test_apps_help(self):
        """Test apps command help."""
        result = runner.invoke(app, ["apps", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "get" in result.stdout
        assert "status" in result.stdout
