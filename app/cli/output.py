"""Output formatting utilities for CLI."""

import json
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.cli.config import get_config

console = Console()
error_console = Console(stderr=True)


def format_timestamp(ts: str | datetime | None) -> str:
    """Format a timestamp for display."""
    if ts is None:
        return "-"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def format_status(status: str) -> Text:
    """Format status with color."""
    colors = {
        "pending": "yellow",
        "processing": "blue",
        "success": "green",
        "failed": "red",
        "healthy": "green",
        "unhealthy": "red",
        "ready": "green",
        "not_ready": "red",
        "alive": "green",
    }
    color = colors.get(status.lower(), "white")
    return Text(status, style=color)


def print_json(data: Any) -> None:
    """Print data as formatted JSON."""
    console.print_json(json.dumps(data, default=str, indent=2))


def print_error(message: str, details: dict | None = None) -> None:
    """Print an error message."""
    error_console.print(f"[red]Error:[/red] {message}")
    if details:
        for key, value in details.items():
            error_console.print(f"  [dim]{key}:[/dim] {value}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_health_status(data: dict, title: str = "Health Status") -> None:
    """Print health status in a formatted panel."""
    config = get_config()
    if config.output_format == "json":
        print_json(data)
        return

    status = data.get("status", "unknown")
    status_text = format_status(status)

    # Main status panel
    panel_content = Text()
    panel_content.append("Status: ")
    panel_content.append(status_text)

    if "timestamp" in data:
        panel_content.append(f"\nTimestamp: {format_timestamp(data['timestamp'])}")

    if "environment" in data:
        panel_content.append(f"\nEnvironment: {data['environment']}")

    console.print(
        Panel(panel_content, title=title, border_style="green" if status == "healthy" else "red")
    )

    # Dependencies table
    if "dependencies" in data or "checks" in data:
        deps = data.get("dependencies", data.get("checks", {}))
        if deps:
            table = Table(title="Dependencies", show_header=True)
            table.add_column("Service", style="cyan")
            table.add_column("Status")

            if isinstance(deps, dict):
                for name, dep_status in deps.items():
                    table.add_row(name, format_status(str(dep_status)))
            elif isinstance(deps, list):
                for dep in deps:
                    name = dep.get("name", dep.get("alias", "unknown"))
                    dep_status = dep.get("status", "unknown")
                    table.add_row(name, format_status(str(dep_status)))

            console.print(table)


def print_applications_table(data: dict, title: str = "Applications") -> None:
    """Print applications in a table format."""
    config = get_config()
    if config.output_format == "json":
        print_json(data)
        return

    apps = data.get("data", data)
    pagination = data.get("pagination", {})

    if not apps:
        print_warning("No applications found")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", max_width=40)
    table.add_column("Company", max_width=25)
    table.add_column("Portal")
    table.add_column("Status")

    for app_id, app_data in apps.items() if isinstance(apps, dict) else enumerate(apps):
        if isinstance(app_data, dict):
            table.add_row(
                str(app_id)[:12] + "..." if len(str(app_id)) > 12 else str(app_id),
                str(app_data.get("title", "-"))[:40],
                str(app_data.get("company_name", app_data.get("company", "-")))[:25],
                str(app_data.get("portal", "-")),
                format_status(app_data.get("status", "unknown")),
            )

    console.print(table)

    # Pagination info
    if pagination:
        total = pagination.get("total_count", "?")
        has_more = pagination.get("has_more", False)
        cursor = pagination.get("next_cursor")

        info = f"Showing {len(apps)} of {total} applications"
        if has_more and cursor:
            info += f" | Next cursor: {cursor[:20]}..."
        console.print(f"[dim]{info}[/dim]")


def print_application_details(data: dict) -> None:
    """Print detailed application information."""
    config = get_config()
    if config.output_format == "json":
        print_json(data)
        return

    # Main info panel
    content = []
    fields = [
        ("ID", "id", "application_id"),
        ("Title", "title"),
        ("Company", "company_name", "company"),
        ("Portal", "portal"),
        ("Status", "status"),
        ("Location", "location"),
        ("Created", "created_at"),
        ("Updated", "updated_at"),
        ("Processed", "processed_at"),
        ("Error", "error_reason"),
    ]

    for field_info in fields:
        label = field_info[0]
        keys = field_info[1:]
        value = None
        for key in keys:
            if key in data and data[key]:
                value = data[key]
                break

        if value:
            if "at" in label.lower() or label in ["Created", "Updated", "Processed"]:
                value = format_timestamp(value)
            elif label == "Status":
                content.append(f"[bold]{label}:[/bold] {format_status(value)}")
                continue
            content.append(f"[bold]{label}:[/bold] {value}")

    console.print(Panel("\n".join(content), title="Application Details", border_style="cyan"))

    # Description if present
    if data.get("description"):
        console.print(Panel(data["description"][:500], title="Description", border_style="dim"))


def print_metrics_summary(metrics_text: str) -> None:
    """Print a summary of Prometheus metrics."""
    config = get_config()
    if config.output_format == "json":
        # Parse metrics into JSON-like structure
        metrics = {}
        for line in metrics_text.split("\n"):
            if line and not line.startswith("#"):
                parts = line.split(" ")
                if len(parts) >= 2:
                    metrics[parts[0]] = parts[1]
        print_json(metrics)
        return

    # Show key metrics in a table
    table = Table(title="Key Metrics", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    key_metrics = [
        "http_requests_total",
        "http_request_duration_seconds",
        "applications_submitted_total",
        "queue_messages_published_total",
        "rate_limit_exceeded_total",
    ]

    for line in metrics_text.split("\n"):
        if line and not line.startswith("#"):
            for metric in key_metrics:
                if line.startswith(metric):
                    parts = line.split(" ")
                    if len(parts) >= 2:
                        table.add_row(parts[0][:60], parts[1])
                    break

    console.print(table)
    console.print(
        f"\n[dim]Total metrics lines: {len([line for line in metrics_text.split(chr(10)) if line and not line.startswith('#')])}[/dim]"
    )
