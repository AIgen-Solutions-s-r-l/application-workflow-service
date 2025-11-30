"""Webhook management commands."""

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.cli.client import APIError, get_client
from app.cli.config import get_config
from app.cli.output import (
    format_timestamp,
    print_error,
    print_info,
    print_json,
    print_success,
    print_warning,
)

app = typer.Typer(help="Webhook management commands")
console = Console()


def format_webhook_status(status: str) -> Text:
    """Format webhook status with color."""
    colors = {
        "active": "green",
        "disabled": "red",
        "paused": "yellow",
    }
    color = colors.get(status.lower(), "white")
    return Text(status, style=color)


def format_delivery_status(status: str) -> Text:
    """Format delivery status with color."""
    colors = {
        "pending": "yellow",
        "delivered": "green",
        "failed": "red",
        "permanently_failed": "red bold",
    }
    color = colors.get(status.lower(), "white")
    return Text(status, style=color)


def print_webhooks_table(webhooks: list, title: str = "Webhooks") -> None:
    """Print webhooks in a table format."""
    config = get_config()
    if config.output_format == "json":
        print_json(webhooks)
        return

    if not webhooks:
        print_warning("No webhooks found")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", max_width=25)
    table.add_column("URL", max_width=40)
    table.add_column("Events", max_width=30)
    table.add_column("Status")
    table.add_column("Deliveries", justify="right")

    for webhook in webhooks:
        events = webhook.get("events", [])
        event_str = ", ".join(e.split(".")[-1] for e in events[:3])
        if len(events) > 3:
            event_str += f" +{len(events) - 3}"

        total = webhook.get("total_deliveries", 0)
        success = webhook.get("successful_deliveries", 0)
        failed = webhook.get("failed_deliveries", 0)
        delivery_str = f"{success}/{total}" if total > 0 else "-"

        table.add_row(
            webhook.get("id", "-")[:16],
            webhook.get("name", "-")[:25] if webhook.get("name") else "-",
            webhook.get("url", "-")[:40],
            event_str,
            format_webhook_status(webhook.get("status", "unknown")),
            delivery_str,
        )

    console.print(table)


def print_webhook_details(webhook: dict, show_secret: bool = False) -> None:
    """Print detailed webhook information."""
    config = get_config()
    if config.output_format == "json":
        print_json(webhook)
        return

    # Main info
    content = []
    content.append(f"[bold]ID:[/bold] {webhook.get('id', '-')}")
    content.append(f"[bold]Name:[/bold] {webhook.get('name', '-') or '-'}")
    content.append(f"[bold]URL:[/bold] {webhook.get('url', '-')}")
    content.append(f"[bold]Status:[/bold] {format_webhook_status(webhook.get('status', 'unknown'))}")

    if webhook.get("description"):
        content.append(f"[bold]Description:[/bold] {webhook['description']}")

    events = webhook.get("events", [])
    content.append(f"[bold]Events:[/bold] {', '.join(events)}")

    content.append(f"[bold]Created:[/bold] {format_timestamp(webhook.get('created_at'))}")
    content.append(f"[bold]Updated:[/bold] {format_timestamp(webhook.get('updated_at'))}")

    if show_secret and webhook.get("secret"):
        content.append(f"\n[bold yellow]Secret:[/bold yellow] {webhook['secret']}")
        content.append("[dim]Save this secret - it won't be shown again![/dim]")

    console.print(Panel("\n".join(content), title="Webhook Details", border_style="cyan"))

    # Statistics
    if webhook.get("total_deliveries", 0) > 0:
        stats_table = Table(title="Delivery Statistics", show_header=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", justify="right")

        stats_table.add_row("Total Deliveries", str(webhook.get("total_deliveries", 0)))
        stats_table.add_row("Successful", str(webhook.get("successful_deliveries", 0)))
        stats_table.add_row("Failed", str(webhook.get("failed_deliveries", 0)))
        stats_table.add_row("Last Delivery", format_timestamp(webhook.get("last_delivery_at")))
        stats_table.add_row("Last Success", format_timestamp(webhook.get("last_success_at")))

        if webhook.get("last_error"):
            stats_table.add_row("Last Error", webhook["last_error"][:50])

        console.print(stats_table)


def print_deliveries_table(deliveries: list, title: str = "Recent Deliveries") -> None:
    """Print deliveries in a table format."""
    config = get_config()
    if config.output_format == "json":
        print_json(deliveries)
        return

    if not deliveries:
        print_warning("No deliveries found")
        return

    table = Table(title=title, show_header=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Event", max_width=25)
    table.add_column("Status")
    table.add_column("Attempts", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Created")
    table.add_column("Error", max_width=30)

    for delivery in deliveries:
        duration = delivery.get("duration_ms")
        duration_str = f"{duration}ms" if duration else "-"

        table.add_row(
            delivery.get("id", "-")[:16],
            delivery.get("event_type", "-"),
            format_delivery_status(delivery.get("status", "unknown")),
            str(delivery.get("attempts", 0)),
            duration_str,
            format_timestamp(delivery.get("created_at")),
            (delivery.get("error", "") or "")[:30] if delivery.get("error") else "-",
        )

    console.print(table)


@app.command("list")
def list_webhooks(
    include_disabled: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include disabled webhooks"),
    ] = False,
) -> None:
    """
    List all webhooks for the current user.
    """
    client = get_client()

    try:
        params = {"include_disabled": include_disabled}
        webhooks = client.get("/webhooks", params=params)
        print_webhooks_table(webhooks)

    except APIError as e:
        if e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to list webhooks: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("get")
def get_webhook(
    webhook_id: Annotated[str, typer.Argument(help="Webhook ID")],
) -> None:
    """
    Get details of a specific webhook.
    """
    client = get_client()

    try:
        webhook = client.get(f"/webhooks/{webhook_id}")
        print_webhook_details(webhook)

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Webhook not found: {webhook_id}")
        elif e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to get webhook: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("create")
def create_webhook(
    url: Annotated[str, typer.Argument(help="Webhook URL (must be HTTPS)")],
    events: Annotated[
        list[str],
        typer.Option(
            "--event", "-e",
            help="Events to subscribe to (can be specified multiple times)",
        ),
    ],
    name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Webhook name"),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Webhook description"),
    ] = None,
) -> None:
    """
    Create a new webhook.

    Available events:
    - application.submitted
    - application.processing
    - application.completed
    - application.failed
    - batch.completed
    - rate_limit.exceeded
    """
    client = get_client()

    payload = {
        "url": url,
        "events": events,
    }
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description

    try:
        webhook = client.post("/webhooks", json=payload)
        print_success("Webhook created successfully")
        print_webhook_details(webhook, show_secret=True)

    except APIError as e:
        if e.status_code == 400:
            print_error(f"Invalid webhook configuration: {e.message}")
        elif e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to create webhook: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("update")
def update_webhook(
    webhook_id: Annotated[str, typer.Argument(help="Webhook ID")],
    url: Annotated[
        Optional[str],
        typer.Option("--url", "-u", help="New webhook URL"),
    ] = None,
    events: Annotated[
        Optional[list[str]],
        typer.Option("--event", "-e", help="New event subscriptions"),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="New webhook name"),
    ] = None,
    enable: Annotated[
        bool,
        typer.Option("--enable", help="Enable the webhook"),
    ] = False,
    disable: Annotated[
        bool,
        typer.Option("--disable", help="Disable the webhook"),
    ] = False,
) -> None:
    """
    Update a webhook's configuration.
    """
    if enable and disable:
        print_error("Cannot specify both --enable and --disable")
        raise typer.Exit(1)

    client = get_client()

    payload = {}
    if url:
        payload["url"] = url
    if events:
        payload["events"] = events
    if name:
        payload["name"] = name
    if enable:
        payload["status"] = "active"
    if disable:
        payload["status"] = "disabled"

    if not payload:
        print_warning("No updates specified")
        raise typer.Exit(0)

    try:
        webhook = client.request("PATCH", f"/webhooks/{webhook_id}", json=payload)
        print_success("Webhook updated successfully")
        print_webhook_details(webhook)

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Webhook not found: {webhook_id}")
        elif e.status_code == 400:
            print_error(f"Invalid update: {e.message}")
        elif e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to update webhook: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("delete")
def delete_webhook(
    webhook_id: Annotated[str, typer.Argument(help="Webhook ID")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation"),
    ] = False,
) -> None:
    """
    Delete a webhook.
    """
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete webhook {webhook_id}?")
        if not confirm:
            print_info("Operation cancelled")
            raise typer.Exit(0)

    client = get_client()

    try:
        client.delete(f"/webhooks/{webhook_id}")
        print_success(f"Webhook {webhook_id} deleted")

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Webhook not found: {webhook_id}")
        elif e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to delete webhook: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("test")
def test_webhook(
    webhook_id: Annotated[str, typer.Argument(help="Webhook ID to test")],
) -> None:
    """
    Send a test event to a webhook.
    """
    client = get_client()

    print_info(f"Sending test event to webhook {webhook_id}...")

    try:
        result = client.post(f"/webhooks/{webhook_id}/test")

        if result.get("success"):
            print_success("Test delivery successful!")
            console.print(f"  Delivery ID: {result.get('delivery_id', '-')}")
            console.print(f"  Response Status: {result.get('response_status', '-')}")
            console.print(f"  Response Time: {result.get('response_time_ms', '-')}ms")
        else:
            print_error("Test delivery failed")
            if result.get("error"):
                console.print(f"  Error: {result['error']}")
            console.print(f"  Delivery ID: {result.get('delivery_id', '-')}")

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Webhook not found: {webhook_id}")
        elif e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to test webhook: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("rotate-secret")
def rotate_secret(
    webhook_id: Annotated[str, typer.Argument(help="Webhook ID")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation"),
    ] = False,
) -> None:
    """
    Rotate the webhook's secret key.

    The old secret will be invalidated immediately.
    """
    if not force:
        print_warning("This will invalidate the current secret immediately!")
        confirm = typer.confirm("Are you sure you want to rotate the secret?")
        if not confirm:
            print_info("Operation cancelled")
            raise typer.Exit(0)

    client = get_client()

    try:
        result = client.post(f"/webhooks/{webhook_id}/rotate-secret")
        print_success("Secret rotated successfully")
        console.print(f"\n[bold yellow]New Secret:[/bold yellow] {result.get('secret', '-')}")
        console.print("[dim]Save this secret - it won't be shown again![/dim]")

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Webhook not found: {webhook_id}")
        elif e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to rotate secret: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("deliveries")
def list_deliveries(
    webhook_id: Annotated[str, typer.Argument(help="Webhook ID")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of deliveries to show"),
    ] = 50,
) -> None:
    """
    List recent deliveries for a webhook.
    """
    client = get_client()

    try:
        params = {"limit": limit}
        deliveries = client.get(f"/webhooks/{webhook_id}/deliveries", params=params)
        print_deliveries_table(deliveries)

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Webhook not found: {webhook_id}")
        elif e.status_code == 503:
            print_error("Webhooks feature is not enabled on this server")
        else:
            print_error(f"Failed to list deliveries: {e.message}", e.details)
        raise typer.Exit(1)
