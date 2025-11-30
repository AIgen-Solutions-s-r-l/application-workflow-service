"""Scheduler management CLI commands."""

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.cli.client import APIError, get_client
from app.cli.config import get_config
from app.cli.output import format_timestamp, print_error, print_info, print_json, print_success

app = typer.Typer(help="Scheduler management commands")
console = Console()


def format_job_status(pending: bool | None) -> Text:
    """Format job status."""
    if pending:
        return Text("paused", style="yellow")
    return Text("active", style="green")


def format_execution_status(status: str) -> Text:
    """Format execution status."""
    colors = {
        "success": "green",
        "failed": "red",
        "warning": "yellow",
        "skipped": "dim",
    }
    return Text(status, style=colors.get(status, "white"))


@app.command("list")
def list_jobs() -> None:
    """
    List all scheduled jobs.
    """
    client = get_client()

    try:
        data = client.get("/scheduler/jobs")

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        jobs = data.get("jobs", [])
        if not jobs:
            print_info("No scheduled jobs found")
            return

        # Status panel
        running = data.get("scheduler_running", False)
        status_text = "[green]Running[/green]" if running else "[red]Stopped[/red]"
        console.print(f"Scheduler Status: {status_text}\n")

        # Jobs table
        table = Table(title="Scheduled Jobs", show_header=True)
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Trigger")
        table.add_column("Next Run")
        table.add_column("Status")

        for job in jobs:
            table.add_row(
                job.get("id", "-"),
                job.get("name", "-"),
                job.get("trigger", "-")[:30],
                format_timestamp(job.get("next_run_time")),
                format_job_status(job.get("pending")),
            )

        console.print(table)

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required")
        elif e.status_code == 503:
            print_error("Scheduler is not enabled on this server")
        else:
            print_error(f"Failed to list jobs: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("status")
def scheduler_status() -> None:
    """
    Show scheduler status.
    """
    client = get_client()

    try:
        data = client.get("/scheduler/status")

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        running = data.get("running", False)
        enabled = data.get("enabled", False)

        content = []
        content.append(f"[bold]Enabled:[/bold] {'Yes' if enabled else 'No'}")
        content.append(f"[bold]Running:[/bold] {'Yes' if running else 'No'}")
        content.append(f"[bold]Job Count:[/bold] {data.get('job_count', 0)}")
        content.append(f"[bold]Timezone:[/bold] {data.get('timezone', 'UTC')}")

        border = "green" if running else "red"
        console.print(Panel("\n".join(content), title="Scheduler Status", border_style=border))

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required")
        else:
            print_error(f"Failed to get status: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("job")
def get_job(
    job_id: Annotated[str, typer.Argument(help="Job ID to look up")],
) -> None:
    """
    Get details of a specific job.
    """
    client = get_client()

    try:
        data = client.get(f"/scheduler/jobs/{job_id}")

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        # Job info
        content = []
        content.append(f"[bold]ID:[/bold] {data.get('id', '-')}")
        content.append(f"[bold]Name:[/bold] {data.get('name', '-')}")
        content.append(f"[bold]Trigger:[/bold] {data.get('trigger', '-')}")
        content.append(f"[bold]Next Run:[/bold] {format_timestamp(data.get('next_run_time'))}")
        content.append(f"[bold]Status:[/bold] {format_job_status(data.get('pending'))}")

        console.print(Panel("\n".join(content), title="Job Details", border_style="cyan"))

        # Stats
        stats = data.get("stats", {})
        if stats:
            stats_table = Table(title="Statistics (Last 7 Days)", show_header=True)
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", justify="right")

            stats_table.add_row("Total Executions", str(stats.get("total", 0)))
            stats_table.add_row("Successful", str(stats.get("success", 0)))
            stats_table.add_row("Failed", str(stats.get("failed", 0)))
            stats_table.add_row("Success Rate", f"{stats.get('success_rate', 0)}%")
            stats_table.add_row("Avg Duration", f"{stats.get('avg_duration_ms', 0)}ms")

            console.print(stats_table)

        # Recent history
        history = data.get("history", [])
        if history:
            history_table = Table(title="Recent Executions", show_header=True)
            history_table.add_column("Time")
            history_table.add_column("Status")
            history_table.add_column("Duration")
            history_table.add_column("Error", max_width=40)

            for entry in history[:10]:
                history_table.add_row(
                    format_timestamp(entry.get("executed_at")),
                    format_execution_status(entry.get("status", "-")),
                    f"{entry.get('duration_ms', 0)}ms",
                    (entry.get("error", "") or "-")[:40],
                )

            console.print(history_table)

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Job not found: {job_id}")
        elif e.status_code == 403:
            print_error("Admin access required")
        else:
            print_error(f"Failed to get job: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("run")
def run_job(
    job_id: Annotated[str, typer.Argument(help="Job ID to run")],
) -> None:
    """
    Trigger immediate execution of a job.
    """
    client = get_client()

    try:
        result = client.post(f"/scheduler/jobs/{job_id}/run")
        print_success(result.get("message", f"Job {job_id} triggered"))

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Job not found: {job_id}")
        elif e.status_code == 403:
            print_error("Admin OPERATOR role required")
        else:
            print_error(f"Failed to run job: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("pause")
def pause_job_cmd(
    job_id: Annotated[str, typer.Argument(help="Job ID to pause")],
) -> None:
    """
    Pause a scheduled job.
    """
    client = get_client()

    try:
        result = client.post(f"/scheduler/jobs/{job_id}/pause")
        print_success(result.get("message", f"Job {job_id} paused"))

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Job not found: {job_id}")
        elif e.status_code == 403:
            print_error("Admin OPERATOR role required")
        else:
            print_error(f"Failed to pause job: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("resume")
def resume_job_cmd(
    job_id: Annotated[str, typer.Argument(help="Job ID to resume")],
) -> None:
    """
    Resume a paused job.
    """
    client = get_client()

    try:
        result = client.post(f"/scheduler/jobs/{job_id}/resume")
        print_success(result.get("message", f"Job {job_id} resumed"))

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Job not found: {job_id}")
        elif e.status_code == 403:
            print_error("Admin OPERATOR role required")
        else:
            print_error(f"Failed to resume job: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("history")
def show_history(
    job_id: Annotated[
        Optional[str],
        typer.Option("--job", "-j", help="Filter by job ID"),
    ] = None,
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="Filter by status"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of results"),
    ] = 20,
) -> None:
    """
    View job execution history.
    """
    client = get_client()

    try:
        if job_id:
            path = f"/scheduler/jobs/{job_id}/history"
        else:
            path = "/scheduler/history"

        params = {"limit": limit}
        if status:
            params["status"] = status

        data = client.get(path, params=params)

        config = get_config()
        if config.output_format == "json":
            print_json(data)
            return

        history = data.get("history", [])
        if not history:
            print_info("No execution history found")
            return

        table = Table(title="Execution History", show_header=True)
        table.add_column("Job ID", style="cyan")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Executed At")
        table.add_column("Error", max_width=30)

        for entry in history:
            table.add_row(
                entry.get("job_id", "-"),
                entry.get("job_name", "-")[:20],
                format_execution_status(entry.get("status", "-")),
                f"{entry.get('duration_ms', 0)}ms",
                format_timestamp(entry.get("executed_at")),
                (entry.get("error", "") or "-")[:30],
            )

        console.print(table)
        console.print(f"\n[dim]Total: {data.get('count', len(history))} entries[/dim]")

    except APIError as e:
        if e.status_code == 403:
            print_error("Admin access required")
        else:
            print_error(f"Failed to get history: {e.message}", e.details)
        raise typer.Exit(1)
