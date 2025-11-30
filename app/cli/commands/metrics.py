"""Metrics commands."""

from typing import Annotated

import typer

from app.cli.client import APIError, get_client
from app.cli.output import console, print_error, print_metrics_summary

app = typer.Typer(help="Metrics commands")


@app.callback(invoke_without_command=True)
def metrics(
    ctx: typer.Context,
    raw: Annotated[
        bool,
        typer.Option("--raw", "-r", help="Show raw Prometheus format"),
    ] = False,
    filter_metric: Annotated[
        str | None,
        typer.Option("--filter", "-f", help="Filter metrics by name pattern"),
    ] = None,
) -> None:
    """
    Display service metrics.

    By default shows a summary of key metrics. Use --raw for full Prometheus output.
    """
    if ctx.invoked_subcommand is not None:
        return

    client = get_client()

    try:
        metrics_text = client.get_metrics()

        if filter_metric:
            lines = []
            for line in metrics_text.split("\n"):
                if filter_metric.lower() in line.lower():
                    lines.append(line)
            metrics_text = "\n".join(lines)

        if raw:
            console.print(metrics_text)
        else:
            print_metrics_summary(metrics_text)

    except APIError as e:
        print_error(f"Failed to get metrics: {e.message}", e.details)
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Failed to get metrics: {str(e)}")
        raise typer.Exit(1)
