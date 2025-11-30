"""Application management commands."""

from typing import Annotated, Optional

import typer

from app.cli.client import APIError, get_client
from app.cli.output import (
    print_application_details,
    print_applications_table,
    print_error,
    print_info,
    print_success,
)

app = typer.Typer(help="Application management commands")


@app.command("list")
def list_apps(
    status: Annotated[
        Optional[str],
        typer.Option(
            "--status", "-s", help="Filter by status (pending, processing, success, failed)"
        ),
    ] = None,
    portal: Annotated[
        Optional[str],
        typer.Option("--portal", "-p", help="Filter by portal (e.g., LinkedIn, Indeed)"),
    ] = None,
    company: Annotated[
        Optional[str],
        typer.Option("--company", "-c", help="Filter by company name"),
    ] = None,
    title: Annotated[
        Optional[str],
        typer.Option("--title", "-t", help="Filter by job title"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of results to return"),
    ] = 20,
    cursor: Annotated[
        Optional[str],
        typer.Option("--cursor", help="Pagination cursor for next page"),
    ] = None,
    failed: Annotated[
        bool,
        typer.Option("--failed", "-f", help="Show failed applications instead of successful"),
    ] = False,
) -> None:
    """
    List applications with optional filters.

    By default shows successful applications. Use --failed to see failed ones.
    """
    client = get_client()

    try:
        if failed or status == "failed":
            data = client.get_failed_applications(
                limit=limit,
                cursor=cursor,
                portal=portal,
            )
            title = "Failed Applications"
        else:
            data = client.get_successful_applications(
                limit=limit,
                cursor=cursor,
                portal=portal,
                company_name=company,
                title=title,
            )
            title = "Successful Applications"

        print_applications_table(data, title=title)

    except APIError as e:
        print_error(f"Failed to list applications: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("get")
def get_app(
    app_id: Annotated[str, typer.Argument(help="Application ID to retrieve")],
    failed: Annotated[
        bool,
        typer.Option("--failed", "-f", help="Look in failed applications"),
    ] = False,
) -> None:
    """
    Get detailed information about a specific application.
    """
    client = get_client()

    try:
        data = client.get_application_details(app_id, failed=failed)
        print_application_details(data)

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Application not found: {app_id}")
            if not failed:
                print_info("Try with --failed flag if looking for a failed application")
        else:
            print_error(f"Failed to get application: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("status")
def get_status(
    app_id: Annotated[str, typer.Argument(help="Application ID to check status")],
) -> None:
    """
    Get the current status of an application.
    """
    client = get_client()

    try:
        data = client.get_application_status(app_id)
        print_application_details(data)

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Application not found: {app_id}")
        else:
            print_error(f"Failed to get status: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("retry")
def retry_app(
    app_id: Annotated[str, typer.Argument(help="Application ID to retry")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force retry without confirmation"),
    ] = False,
) -> None:
    """
    Retry a failed application by re-queuing it.

    This command re-submits a failed application for processing.
    """
    if not force:
        confirm = typer.confirm(f"Are you sure you want to retry application {app_id}?")
        if not confirm:
            print_info("Operation cancelled")
            raise typer.Exit(0)

    client = get_client()

    try:
        # Note: This endpoint may need to be implemented in the API
        data = client.post(f"/applications/{app_id}/retry")
        print_success(f"Application {app_id} has been re-queued for processing")
        if "status" in data:
            print_info(f"New status: {data['status']}")

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Application not found: {app_id}")
        elif e.status_code == 400:
            print_error(f"Cannot retry application: {e.message}")
        else:
            print_error(f"Failed to retry application: {e.message}", e.details)
        raise typer.Exit(1)


@app.command("cancel")
def cancel_app(
    app_id: Annotated[str, typer.Argument(help="Application ID to cancel")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force cancel without confirmation"),
    ] = False,
) -> None:
    """
    Cancel a pending application.

    Only pending applications can be cancelled.
    """
    if not force:
        confirm = typer.confirm(f"Are you sure you want to cancel application {app_id}?")
        if not confirm:
            print_info("Operation cancelled")
            raise typer.Exit(0)

    client = get_client()

    try:
        # Note: This endpoint may need to be implemented in the API
        client.delete(f"/applications/{app_id}")
        print_success(f"Application {app_id} has been cancelled")

    except APIError as e:
        if e.status_code == 404:
            print_error(f"Application not found: {app_id}")
        elif e.status_code == 400:
            print_error(f"Cannot cancel application: {e.message}")
        else:
            print_error(f"Failed to cancel application: {e.message}", e.details)
        raise typer.Exit(1)
