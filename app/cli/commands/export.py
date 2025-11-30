"""Export commands."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from app.cli.client import APIError, get_client
from app.cli.output import print_error, print_success

app = typer.Typer(help="Data export commands")


def _build_export_params(
    portal: str | None,
    date_from: str | None,
    date_to: str | None,
    include_successful: bool,
    include_failed: bool,
) -> dict:
    """Build query parameters for export."""
    params = {}
    if portal:
        params["portal"] = portal
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    params["include_successful"] = str(include_successful).lower()
    params["include_failed"] = str(include_failed).lower()
    return params


@app.command("csv")
def export_csv(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (default: stdout)"),
    ] = None,
    portal: Annotated[
        str | None,
        typer.Option("--portal", "-p", help="Filter by portal"),
    ] = None,
    date_from: Annotated[
        str | None,
        typer.Option("--from", help="Filter from date (YYYY-MM-DD)"),
    ] = None,
    date_to: Annotated[
        str | None,
        typer.Option("--to", help="Filter to date (YYYY-MM-DD)"),
    ] = None,
    include_successful: Annotated[
        bool,
        typer.Option("--successful/--no-successful", help="Include successful applications"),
    ] = True,
    include_failed: Annotated[
        bool,
        typer.Option("--failed/--no-failed", help="Include failed applications"),
    ] = True,
) -> None:
    """
    Export applications to CSV format.

    If no output file is specified, prints to stdout.
    """
    client = get_client()
    params = _build_export_params(portal, date_from, date_to, include_successful, include_failed)

    try:
        import httpx

        url = f"{client.base_url}/export/csv"
        headers = client._get_headers()

        with httpx.Client(timeout=client.timeout) as http_client:
            response = http_client.get(url, headers=headers, params=params)

            if response.status_code >= 400:
                raise APIError(response.status_code, response.text)

            content = response.text

            if output:
                output.write_text(content)
                print_success(f"Exported to {output}")
            else:
                print(content)

    except APIError as e:
        print_error(f"Export failed: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("excel")
def export_excel(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path"),
    ] = Path(f"applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"),
    portal: Annotated[
        str | None,
        typer.Option("--portal", "-p", help="Filter by portal"),
    ] = None,
    date_from: Annotated[
        str | None,
        typer.Option("--from", help="Filter from date (YYYY-MM-DD)"),
    ] = None,
    date_to: Annotated[
        str | None,
        typer.Option("--to", help="Filter to date (YYYY-MM-DD)"),
    ] = None,
    include_successful: Annotated[
        bool,
        typer.Option("--successful/--no-successful", help="Include successful applications"),
    ] = True,
    include_failed: Annotated[
        bool,
        typer.Option("--failed/--no-failed", help="Include failed applications"),
    ] = True,
) -> None:
    """
    Export applications to Excel format.
    """
    client = get_client()
    params = _build_export_params(portal, date_from, date_to, include_successful, include_failed)

    try:
        import httpx

        url = f"{client.base_url}/export/excel"
        headers = client._get_headers()

        with httpx.Client(timeout=client.timeout) as http_client:
            response = http_client.get(url, headers=headers, params=params)

            if response.status_code >= 400:
                raise APIError(response.status_code, response.text)

            output.write_bytes(response.content)
            print_success(f"Exported to {output}")

    except APIError as e:
        print_error(f"Export failed: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("summary")
def export_summary() -> None:
    """
    Show export summary (counts and available portals).
    """
    client = get_client()

    try:
        data = client.get("/export/summary")

        from rich.panel import Panel

        from app.cli.output import console

        content = [
            f"[bold]Total Applications:[/bold] {data.get('total_applications', '-')}",
            f"[bold]Successful:[/bold] [green]{data.get('successful_applications', '-')}[/green]",
            f"[bold]Failed:[/bold] [red]{data.get('failed_applications', '-')}[/red]",
            "",
            "[bold]Available Portals:[/bold]",
        ]

        portals = data.get("available_portals", [])
        for portal in portals:
            content.append(f"  • {portal}")

        if not portals:
            content.append("  [dim]No portals found[/dim]")

        content.append("")
        content.append("[bold]Export Formats:[/bold]")
        for fmt in data.get("export_formats", ["csv", "excel"]):
            content.append(f"  • {fmt}")

        console.print(Panel("\n".join(content), title="Export Summary", border_style="cyan"))

    except APIError as e:
        print_error(f"Failed to get export summary: {e.message}", e.details)
        raise typer.Exit(1)
