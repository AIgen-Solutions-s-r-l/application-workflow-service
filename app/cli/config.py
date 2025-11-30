"""CLI configuration management."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class CLIConfig(BaseSettings):
    """CLI configuration loaded from environment or config file."""

    # API connection
    api_url: str = Field(
        default="http://localhost:8009",
        description="Application Manager Service API URL",
    )
    api_token: str | None = Field(
        default=None,
        description="JWT token for authentication",
    )
    api_timeout: int = Field(
        default=30,
        description="API request timeout in seconds",
    )

    # Output settings
    output_format: str = Field(
        default="table",
        description="Default output format (table, json, csv)",
    )
    no_color: bool = Field(
        default=False,
        description="Disable colored output",
    )

    model_config = {
        "env_prefix": "APP_MANAGER_",
        "env_file": ".env",
        "extra": "ignore",
    }


def get_config_dir() -> Path:
    """Get the CLI configuration directory."""
    config_dir = Path.home() / ".config" / "app-manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the CLI configuration file path."""
    return get_config_dir() / "config.env"


def load_config() -> CLIConfig:
    """Load CLI configuration from environment and config file."""
    config_file = get_config_file()

    # Load from config file if exists
    if config_file.exists():
        # Read config file and set as environment variables
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Don't override existing env vars
                    if key not in os.environ:
                        os.environ[key] = value.strip('"').strip("'")

    return CLIConfig()


def save_config(key: str, value: str) -> None:
    """Save a configuration value to the config file."""
    config_file = get_config_file()
    config = {}

    # Load existing config
    if config_file.exists():
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k] = v

    # Update value
    env_key = f"APP_MANAGER_{key.upper()}"
    config[env_key] = value

    # Write back
    with open(config_file, "w") as f:
        for k, v in sorted(config.items()):
            f.write(f"{k}={v}\n")


# Global config instance
_config: CLIConfig | None = None


def get_config() -> CLIConfig:
    """Get the global CLI configuration."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
