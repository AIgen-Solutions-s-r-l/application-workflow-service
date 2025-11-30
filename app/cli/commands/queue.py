"""Queue management commands."""

from typing import Annotated

import typer
from rich.table import Table

from app.cli.client import APIError, get_client
from app.cli.output import (
    console,
    print_error,
    print_info,
    print_json,
    print_success,
    print_warning,
)

app = typer.Typer(help="Queue management commands")


@app.command("status")
def queue_status(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """
    Show queue status including depth and consumer count.
    """
    client = get_client()

    try:
        # Note: This endpoint may need to be implemented in the API
        data = client.get("/queue/status")

        if json_output:
            print_json(data)
            return

        table = Table(title="Queue Status", show_header=True)
        table.add_column("Queue", style="cyan")
        table.add_column("Messages", justify="right")
        table.add_column("Consumers", justify="right")
        table.add_column("Rate (msg/s)", justify="right")

        queues = data.get("queues", [data] if "name" in data else [])
        for queue in queues:
            table.add_row(
                queue.get("name", "application_processing_queue"),
                str(queue.get("messages", queue.get("message_count", "-"))),
                str(queue.get("consumers", queue.get("consumer_count", "-"))),
                str(queue.get("rate", "-")),
            )

        console.print(table)

        # DLQ info
        dlq = data.get("dlq", {})
        if dlq:
            dlq_count = dlq.get("messages", dlq.get("message_count", 0))
            if dlq_count > 0:
                print_warning(f"Dead Letter Queue has {dlq_count} messages")
            else:
                print_success("Dead Letter Queue is empty")

    except APIError as e:
        if e.status_code == 404:
            print_error("Queue status endpoint not available")
            print_info("This feature requires the queue status API endpoint")
        else:
            print_error(f"Failed to get queue status: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("purge-dlq")
def purge_dlq(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force purge without confirmation"),
    ] = False,
) -> None:
    """
    Purge all messages from the Dead Letter Queue.

    WARNING: This permanently deletes failed messages!
    """
    if not force:
        print_warning("This will permanently delete all messages in the Dead Letter Queue!")
        confirm = typer.confirm("Are you sure you want to continue?")
        if not confirm:
            print_info("Operation cancelled")
            raise typer.Exit(0)

    client = get_client()

    try:
        # Note: This endpoint may need to be implemented in the API
        data = client.delete("/queue/dlq")
        purged_count = data.get("purged", data.get("count", "unknown"))
        print_success(f"Purged {purged_count} messages from DLQ")

    except APIError as e:
        if e.status_code == 404:
            print_error("DLQ purge endpoint not available")
            print_info("This feature requires the queue management API endpoint")
        else:
            print_error(f"Failed to purge DLQ: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("reprocess-dlq")
def reprocess_dlq(
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Maximum number of messages to reprocess"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess without confirmation"),
    ] = False,
) -> None:
    """
    Move messages from DLQ back to the main processing queue.

    Messages will be retried for processing.
    """
    if not force:
        msg = "This will move DLQ messages back to the processing queue"
        if limit:
            msg += f" (max {limit} messages)"
        print_info(msg)
        confirm = typer.confirm("Are you sure you want to continue?")
        if not confirm:
            print_info("Operation cancelled")
            raise typer.Exit(0)

    client = get_client()

    try:
        # Note: This endpoint may need to be implemented in the API
        params = {"limit": limit} if limit else None
        data = client.post("/queue/dlq/reprocess", params=params)
        moved_count = data.get("moved", data.get("count", "unknown"))
        print_success(f"Moved {moved_count} messages from DLQ to processing queue")

    except APIError as e:
        if e.status_code == 404:
            print_error("DLQ reprocess endpoint not available")
            print_info("This feature requires the queue management API endpoint")
        else:
            print_error(f"Failed to reprocess DLQ: {e.message}", e.details)
        raise typer.Exit(1)
