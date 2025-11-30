"""Configuration management commands."""

from typing import Annotated

import typer

from app.cli.config import get_config, get_config_file, save_config
from app.cli.output import console, print_error, print_info, print_success

app = typer.Typer(help="Configuration management commands")


@app.command("show")
def show_config() -> None:
    """
    Show current configuration.
    """
    config = get_config()
    config_file = get_config_file()

    console.print("[bold]Current Configuration[/bold]\n")
    console.print(f"Config file: {config_file}")
    console.print(f"File exists: {config_file.exists()}\n")

    console.print("[bold]Settings:[/bold]")
    console.print(f"  API URL:    {config.api_url}")
    console.print(f"  API Token:  {'[set]' if config.api_token else '[not set]'}")
    console.print(f"  Timeout:    {config.api_timeout}s")
    console.print(f"  Output:     {config.output_format}")
    console.print(f"  No Color:   {config.no_color}")


@app.command("set")
def set_config(
    key: Annotated[str, typer.Argument(help="Configuration key (url, token, timeout, output)")],
    value: Annotated[str, typer.Argument(help="Configuration value")],
) -> None:
    """
    Set a configuration value.

    Available keys:
    - url: API URL
    - token: JWT authentication token
    - timeout: Request timeout in seconds
    - output: Default output format (table, json)
    """
    key_mapping = {
        "url": "api_url",
        "token": "api_token",
        "timeout": "api_timeout",
        "output": "output_format",
    }

    if key.lower() not in key_mapping:
        print_error(f"Unknown configuration key: {key}")
        print_info(f"Valid keys: {', '.join(key_mapping.keys())}")
        raise typer.Exit(1)

    actual_key = key_mapping[key.lower()]

    # Validate value
    if actual_key == "api_timeout":
        try:
            int(value)
        except ValueError:
            print_error("Timeout must be a number")
            raise typer.Exit(1)

    if actual_key == "output_format" and value not in ("table", "json", "csv"):
        print_error("Output format must be one of: table, json, csv")
        raise typer.Exit(1)

    save_config(actual_key, value)
    print_success(f"Set {key} = {value if key != 'token' else '[hidden]'}")


@app.command("get")
def get_config_value(
    key: Annotated[str, typer.Argument(help="Configuration key to retrieve")],
) -> None:
    """
    Get a configuration value.
    """
    config = get_config()

    key_mapping = {
        "url": "api_url",
        "token": "api_token",
        "timeout": "api_timeout",
        "output": "output_format",
    }

    if key.lower() not in key_mapping:
        print_error(f"Unknown configuration key: {key}")
        print_info(f"Valid keys: {', '.join(key_mapping.keys())}")
        raise typer.Exit(1)

    actual_key = key_mapping[key.lower()]
    value = getattr(config, actual_key, None)

    if key.lower() == "token" and value:
        console.print("[set - hidden for security]")
    else:
        console.print(value or "[not set]")


@app.command("reset")
def reset_config(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reset without confirmation"),
    ] = False,
) -> None:
    """
    Reset configuration to defaults.
    """
    config_file = get_config_file()

    if not config_file.exists():
        print_info("No configuration file exists")
        return

    if not force:
        confirm = typer.confirm("Are you sure you want to reset configuration?")
        if not confirm:
            print_info("Operation cancelled")
            raise typer.Exit(0)

    config_file.unlink()
    print_success("Configuration reset to defaults")
