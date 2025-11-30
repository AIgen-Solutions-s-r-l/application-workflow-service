"""Health check commands."""

import typer

from app.cli.client import APIError, get_client
from app.cli.output import print_error, print_health_status

app = typer.Typer(help="Health check commands")


@app.callback(invoke_without_command=True)
def health(
    ctx: typer.Context,
    live: bool = typer.Option(False, "--live", "-l", help="Check liveness only"),
    ready: bool = typer.Option(False, "--ready", "-r", help="Check readiness only"),
) -> None:
    """
    Check service health status.

    Without flags, returns full health status including all dependencies.
    """
    if ctx.invoked_subcommand is not None:
        return

    client = get_client()

    try:
        if live:
            data = client.health_live()
            print_health_status(data, title="Liveness Check")
        elif ready:
            data = client.health_ready()
            print_health_status(data, title="Readiness Check")
        else:
            data = client.health()
            print_health_status(data, title="Health Status")

        # Exit with error code if unhealthy
        status = data.get("status", "unknown").lower()
        if status not in ("healthy", "ready", "alive"):
            raise typer.Exit(1)

    except APIError as e:
        print_error(f"Health check failed: {e.message}", e.details)
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Connection failed: {str(e)}")
        raise typer.Exit(1)
