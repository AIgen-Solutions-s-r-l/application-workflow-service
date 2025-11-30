"""CLI entry point for Application Manager Service."""

from typing import Annotated, Optional

import typer
from rich.console import Console

from app.cli.commands import apps, config, export, health, metrics, queue

# Version from pyproject.toml
__version__ = "1.0.0"

# Create main app
app = typer.Typer(
    name="app-manager",
    help="Application Manager Service CLI - Manage job applications and workflows",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register sub-commands
app.add_typer(health.app, name="health", help="Health check commands")
app.add_typer(apps.app, name="apps", help="Application management")
app.add_typer(queue.app, name="queue", help="Queue management")
app.add_typer(export.app, name="export", help="Data export")
app.add_typer(metrics.app, name="metrics", help="Service metrics")
app.add_typer(config.app, name="config", help="Configuration management")

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"app-manager version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
    api_url: Annotated[
        Optional[str],
        typer.Option("--api-url", "-u", envvar="APP_MANAGER_API_URL", help="API URL"),
    ] = None,
    token: Annotated[
        Optional[str],
        typer.Option("--token", "-t", envvar="APP_MANAGER_API_TOKEN", help="JWT token"),
    ] = None,
    output_format: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output format (table, json)"),
    ] = None,
) -> None:
    """
    Application Manager Service CLI.

    Manage job applications, check service health, view metrics, and export data.

    [bold]Quick Start:[/bold]

        # Check service health
        app-manager health

        # List successful applications
        app-manager apps list

        # Get application details
        app-manager apps get <app_id>

        # View metrics
        app-manager metrics

        # Export to CSV
        app-manager export csv -o applications.csv

    [bold]Configuration:[/bold]

        # Set API URL
        app-manager config set url http://localhost:8009

        # Set authentication token
        app-manager config set token <your-jwt-token>

    [bold]Environment Variables:[/bold]

        APP_MANAGER_API_URL    - API URL
        APP_MANAGER_API_TOKEN  - JWT authentication token
        APP_MANAGER_API_TIMEOUT - Request timeout (seconds)
    """
    # Override config with CLI options
    import os

    if api_url:
        os.environ["APP_MANAGER_API_URL"] = api_url
    if token:
        os.environ["APP_MANAGER_API_TOKEN"] = token
    if output_format:
        os.environ["APP_MANAGER_OUTPUT_FORMAT"] = output_format

    # Reset cached config
    from app.cli.client import reset_client

    reset_client()


if __name__ == "__main__":
    app()
