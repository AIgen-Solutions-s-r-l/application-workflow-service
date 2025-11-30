"""Admin dashboard CLI commands."""

from datetime import datetime
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.cli.client import APIError, get_client
from app.cli.config import get_config
from app.cli.output import format_timestamp, print_error, print_info, print_json, print_success

app = typer.Typer(help="Admin dashboard commands")
console = Console()


def format_health_status(status: str) -> Text:
    """Format health status with color."""
    colors = {
        "healthy": "green",
        "unhealthy": "red",
        "warning": "yellow",
        "unavailable": "dim",
    }
    color = colors.get(status.lower(), "white")
    return Text(status, style=color)


def print_dashboard(data: dict) -> None:
    """Print dashboard summary."""
    config = get_config()
    if config.output_format == "json":
        print_json(data)
        return

    # Summary panel
    summary = data.get("summary", {})
    content = []
    content.append(f"[bold]Total Users:[/bold] {summary.get('total_users', 0)}")
    content.append(f"[bold]Active Users (24h):[/bold] {summary.get('active_users_24h', 0)}")
    content.append(f"[bold]Total Applications:[/bold] {summary.get('total_applications', 0)}")
    content.append(f"[bold]Applications Today:[/bold] {summary.get('applications_today', 0)}")
    content.append(f"[bold]Success Rate:[/bold] {summary.get('success_rate', 0)}%")
    content.append(f"[bold]Avg Processing Time:[/bold] {summary.get('avg_processing_time_seconds', 0)}s")

    console.print(Panel("\n".join(content), title="Dashboard Summary", border_style="cyan"))

    # Breakdown
    breakdown = data.get("breakdown", {})
    if breakdown:
        breakdown_table = Table(title="Application Breakdown", show_header=True)
        breakdown_table.add_column("Status", style="cyan")
        breakdown_table.add_column("Count", justify="right")

        for status, count in breakdown.items():
            breakdown_table.add_row(status.capitalize(), str(count))

        console.print(breakdown_table)

    # Health status
    health = data.get("health", {})
    if health:
        health_table = Table(title="System Health", show_header=True)
        health_table.add_column("Service", style="cyan")
        health_table.add_column("Status")

        for service, status in health.items():
            health_table.add_row(service, format_health_status(status))

        console.print(health_table)

    # Queue info
    queues = data.get("queues", {})
    if queues:
        queue_table = Table(title="Queue Status", show_header=True)
        queue_table.add_column("Queue", style="cyan")
        queue_table.add_column("Depth", justify="right")

        proc = queues.get("processing", {})
        queue_table.add_row("Processing", str(proc.get("depth", 0)))

        dlq = queues.get("dlq", {})
        queue_table.add_row("DLQ", str(dlq.get("depth", 0)))

        console.print(queue_table)


def print_users_table(data: dict, title: str = "Users") -> None:
    """Print users table."""
    config = get_config()
    if config.output_format == "json":
        print_json(data)
        return

    users = data.get("users", [])
    if not users:
        print_info("No users found")
        return

    table = Table(title=title, show_header=True)
    table.add_column("User ID", style="cyan")
    table.add_column("Total Apps", justify="right")
    table.add_column("Successful", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Success Rate", justify="right")
    table.add_column("Last Active")

    for user in users:
        table.add_row(
            str(user.get("user_id", "-"))[:20],
            str(user.get("total_applications", 0)),
            str(user.get("successful", 0)),
            str(user.get("failed", 0)),
            f"{user.get('success_rate', 0)}%",
            format_timestamp(user.get("last_active")),
        )

    console.print(table)

    pagination = data.get("pagination", {})
    if pagination:
        total = pagination.get("total", 0)
        console.print(f"[dim]Total: {total} users[/dim]")


@app.command("dashboard")
def dashboard() -> None:
    """
    Show admin dashboard summary.

    Displays key metrics including user counts, application statistics,
    queue depths, and system health.
    """
    client = get_client()

    try:
        data = client.get("/admin/dashboard")
        print_dashboard(data)

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required")
        elif e.status_code == 503:
            print_error("Admin features are not enabled on this server")
        else:
            print_error(f"Failed to get dashboard: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("users")
def list_users(
    search: Annotated[
        Optional[str],
        typer.Option("--search", "-s", help="Search by user ID"),
    ] = None,
    sort: Annotated[
        str,
        typer.Option("--sort", help="Sort by: total_applications, last_active"),
    ] = "total_applications",
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of results"),
    ] = 20,
) -> None:
    """
    List users with their application statistics.
    """
    client = get_client()

    try:
        params = {"sort": sort, "limit": limit}
        if search:
            params["search"] = search

        data = client.get("/admin/users", params=params)
        print_users_table(data)

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required")
        elif e.status_code == 503:
            print_error("Admin features are not enabled on this server")
        else:
            print_error(f"Failed to list users: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("user")
def get_user(
    user_id: Annotated[str, typer.Argument(help="User ID to look up")],
) -> None:
    """
    Get detailed information about a specific user.
    """
    client = get_client()

    try:
        data = client.get(f"/admin/users/{user_id}")

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        # User info panel
        stats = data.get("statistics", {})
        content = []
        content.append(f"[bold]User ID:[/bold] {data.get('user_id', '-')}")
        content.append(f"[bold]Total Applications:[/bold] {stats.get('total_applications', 0)}")
        content.append(f"[bold]Pending:[/bold] {stats.get('pending', 0)}")
        content.append(f"[bold]Successful:[/bold] {stats.get('successful', 0)}")
        content.append(f"[bold]Failed:[/bold] {stats.get('failed', 0)}")
        content.append(f"[bold]Success Rate:[/bold] {stats.get('success_rate', 0)}%")
        content.append(f"[bold]Webhooks:[/bold] {data.get('webhooks_count', 0)}")

        console.print(Panel("\n".join(content), title="User Details", border_style="cyan"))

        # Recent applications
        recent = data.get("recent_applications", [])
        if recent:
            table = Table(title="Recent Applications", show_header=True)
            table.add_column("ID", style="cyan")
            table.add_column("Status")
            table.add_column("Portal")
            table.add_column("Created")

            for app in recent:
                table.add_row(
                    str(app.get("id", "-"))[:12],
                    app.get("status", "-"),
                    app.get("portal", "-"),
                    format_timestamp(app.get("created_at")),
                )

            console.print(table)

    except APIError as e:
        if e.status_code == 404:
            print_error(f"User not found: {user_id}")
        elif e.status_code == 403:
            print_error("Admin access required")
        else:
            print_error(f"Failed to get user: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("analytics")
def analytics(
    type_: Annotated[
        str,
        typer.Argument(help="Analytics type: applications, users, errors"),
    ] = "applications",
    period: Annotated[
        str,
        typer.Option("--period", "-p", help="Period: hour, day, week, month"),
    ] = "day",
) -> None:
    """
    View analytics data.
    """
    client = get_client()

    try:
        if type_ == "applications":
            data = client.get("/admin/analytics/applications", params={"period": period})
        elif type_ == "users":
            data = client.get("/admin/analytics/users")
        elif type_ == "errors":
            data = client.get("/admin/analytics/errors")
        else:
            print_error(f"Unknown analytics type: {type_}")
            raise typer.Exit(1)

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        # Print totals
        if "totals" in data:
            totals = data["totals"]
            console.print(Panel(
                f"Total: {totals.get('total', 0)} | "
                f"Success: {totals.get('success', 0)} | "
                f"Failed: {totals.get('failed', 0)} | "
                f"Rate: {totals.get('success_rate', 0)}%",
                title=f"Analytics ({type_})",
                border_style="cyan",
            ))

        # Print breakdown if available
        if "breakdown" in data:
            table = Table(title="Breakdown", show_header=True)
            table.add_column("Value", style="cyan")
            table.add_column("Count", justify="right")

            for item in data["breakdown"][:10]:
                table.add_row(str(item.get("value", "-")), str(item.get("count", 0)))

            console.print(table)

        # Print error breakdown for error analytics
        if "error_breakdown" in data:
            table = Table(title="Error Breakdown", show_header=True)
            table.add_column("Error Type", style="red")
            table.add_column("Count", justify="right")
            table.add_column("Percentage", justify="right")

            for item in data["error_breakdown"]:
                table.add_row(
                    str(item.get("error_type", "-"))[:40],
                    str(item.get("count", 0)),
                    f"{item.get('percentage', 0)}%",
                )

            console.print(table)

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required")
        elif e.status_code == 503:
            print_error("Admin features are not enabled on this server")
        else:
            print_error(f"Failed to get analytics: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("queues")
def queues() -> None:
    """
    Show queue status.
    """
    client = get_client()

    try:
        data = client.get("/admin/queues")

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        queues_list = data.get("queues", [])
        if not queues_list:
            print_info("No queues found")
            return

        table = Table(title="Queue Status", show_header=True)
        table.add_column("Queue", style="cyan")
        table.add_column("Depth", justify="right")
        table.add_column("Pending", justify="right")
        table.add_column("Processing", justify="right")
        table.add_column("Status")

        for queue in queues_list:
            status = queue.get("status", "unknown")
            status_text = Text(status, style="green" if status == "healthy" else "yellow")

            table.add_row(
                queue.get("name", "-"),
                str(queue.get("depth", 0)),
                str(queue.get("pending", "-")),
                str(queue.get("processing", "-")),
                status_text,
            )

        console.print(table)

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required")
        else:
            print_error(f"Failed to get queues: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("system")
def system_info() -> None:
    """
    Show system configuration and info.
    """
    client = get_client()

    try:
        data = client.get("/admin/system")

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        # Basic info
        content = []
        content.append(f"[bold]Service:[/bold] {data.get('service_name', '-')}")
        content.append(f"[bold]Environment:[/bold] {data.get('environment', '-')}")
        content.append(f"[bold]Debug:[/bold] {data.get('debug', False)}")

        console.print(Panel("\n".join(content), title="System Info", border_style="cyan"))

        # Features
        features = data.get("features", {})
        if features:
            table = Table(title="Features", show_header=True)
            table.add_column("Feature", style="cyan")
            table.add_column("Enabled")

            for feature, enabled in features.items():
                status = Text("Yes", style="green") if enabled else Text("No", style="red")
                table.add_row(feature.replace("_", " ").title(), status)

            console.print(table)

        # API Versions
        versions = data.get("api_versions", {})
        if versions:
            console.print(f"\n[bold]API Versions:[/bold]")
            console.print(f"  Supported: {', '.join(versions.get('supported', []))}")
            console.print(f"  Default: {versions.get('default', '-')}")
            if versions.get("deprecated"):
                console.print(f"  Deprecated: {', '.join(versions.get('deprecated', []))}")

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required (ADMIN role)")
        else:
            print_error(f"Failed to get system info: {e.message}", e.details)
        raise typer.Exit(1)
