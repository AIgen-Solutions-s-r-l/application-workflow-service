"""Tests for CLI configuration."""

import os
from pathlib import Path
from unittest.mock import patch

from app.cli.config import CLIConfig, get_config_dir, load_config, save_config


class TestCLIConfig:
    """Tests for CLIConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CLIConfig()
        assert config.api_url == "http://localhost:8009"
        assert config.api_token is None
        assert config.api_timeout == 30
        assert config.output_format == "table"
        assert config.no_color is False

    def test_from_environment(self):
        """Test loading config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "APP_MANAGER_API_URL": "http://test:9000",
                "APP_MANAGER_API_TOKEN": "test-token",
                "APP_MANAGER_API_TIMEOUT": "60",
            },
        ):
            config = CLIConfig()
            assert config.api_url == "http://test:9000"
            assert config.api_token == "test-token"
            assert config.api_timeout == 60


class TestConfigDirectory:
    """Tests for config directory functions."""

    def test_get_config_dir(self):
        """Test config directory path."""
        config_dir = get_config_dir()
        assert config_dir == Path.home() / ".config" / "app-manager"

    def test_get_config_dir_creates_directory(self, tmp_path):
        """Test that config directory is created if it doesn't exist."""
        with patch("app.cli.config.Path.home", return_value=tmp_path):
            config_dir = get_config_dir()
            assert config_dir.exists()


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_config_creates_file(self, tmp_path):
        """Test that save_config creates config file."""
        config_file = tmp_path / ".config" / "app-manager" / "config.env"

        with patch("app.cli.config.get_config_file", return_value=config_file):
            config_file.parent.mkdir(parents=True, exist_ok=True)
            save_config("api_url", "http://test:9000")

            assert config_file.exists()
            content = config_file.read_text()
            assert "APP_MANAGER_API_URL=http://test:9000" in content

    def test_save_config_preserves_existing(self, tmp_path):
        """Test that save_config preserves existing values."""
        config_file = tmp_path / "config.env"
        config_file.write_text("APP_MANAGER_API_TOKEN=existing-token\n")

        with patch("app.cli.config.get_config_file", return_value=config_file):
            save_config("api_url", "http://test:9000")

            content = config_file.read_text()
            assert "APP_MANAGER_API_TOKEN=existing-token" in content
            assert "APP_MANAGER_API_URL=http://test:9000" in content


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_file(self, tmp_path):
        """Test loading config from file."""
        config_file = tmp_path / ".config" / "app-manager" / "config.env"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("APP_MANAGER_API_URL=http://file:9000\n")

        # Clear any existing env var
        env = os.environ.copy()
        env.pop("APP_MANAGER_API_URL", None)

        with (
            patch("app.cli.config.get_config_file", return_value=config_file),
            patch.dict(os.environ, env, clear=True),
        ):
            config = load_config()
            assert config.api_url == "http://file:9000"

    def test_load_config_env_takes_precedence(self, tmp_path):
        """Test that environment variables take precedence over config file."""
        config_file = tmp_path / ".config" / "app-manager" / "config.env"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("APP_MANAGER_API_URL=http://file:9000\n")

        with (
            patch("app.cli.config.get_config_file", return_value=config_file),
            patch.dict(os.environ, {"APP_MANAGER_API_URL": "http://env:9000"}),
        ):
            config = load_config()
            assert config.api_url == "http://env:9000"
