"""
Migration CLI commands for managing database migrations.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

migrate_app = typer.Typer(name="migrate", help="Database migration commands")
console = Console()


def get_db():
    """Get database connection."""
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.core.config import settings

    client = AsyncIOMotorClient(settings.mongodb)
    return client[settings.mongodb_database]


def get_runner():
    """Get migration runner instance."""
    from app.migrations.runner import MigrationRunner

    db = get_db()
    return MigrationRunner(db)


@migrate_app.command("status")
def status():
    """Show current migration status."""

    async def _status():
        runner = get_runner()
        await runner.initialize()
        return await runner.get_status()

    try:
        result = asyncio.get_event_loop().run_until_complete(_status())

        # Summary
        console.print()
        console.print("[bold]Migration Status[/bold]")
        console.print(f"  Current Version: [cyan]{result['current_version']}[/cyan]")
        console.print(f"  Latest Version:  [cyan]{result['latest_version']}[/cyan]")
        console.print(f"  Applied:         [green]{result['applied_count']}[/green]")
        console.print(f"  Pending:         [yellow]{result['pending_count']}[/yellow]")
        console.print()

        # Applied migrations table
        if result["applied"]:
            table = Table(title="Applied Migrations", show_header=True)
            table.add_column("Version", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Applied At", style="green")
            table.add_column("Time (ms)", style="dim")

            for m in result["applied"]:
                table.add_row(
                    str(m["version"]),
                    m["name"],
                    m["applied_at"],
                    str(m["execution_time_ms"]),
                )

            console.print(table)
            console.print()

        # Pending migrations table
        if result["pending"]:
            table = Table(title="Pending Migrations", show_header=True)
            table.add_column("Version", style="yellow")
            table.add_column("Name", style="white")
            table.add_column("Description", style="dim")

            for m in result["pending"]:
                table.add_row(str(m["version"]), m["name"], m["description"])

            console.print(table)
        else:
            console.print("[green]All migrations are up to date![/green]")

    except Exception as e:
        console.print(f"[red]Error: Failed to get migration status: {e}[/red]")
        raise typer.Exit(1)


@migrate_app.command("up")
def up(
    target: Annotated[
        Optional[int],
        typer.Option("--target", "-t", help="Target version to migrate to"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be done without applying"),
    ] = False,
):
    """Apply pending migrations."""

    async def _up():
        runner = get_runner()
        await runner.initialize()
        return await runner.migrate_up(target_version=target, dry_run=dry_run)

    try:
        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
            console.print()

        records = asyncio.get_event_loop().run_until_complete(_up())

        if not records and not dry_run:
            console.print("[green]No pending migrations to apply.[/green]")
            return

        if not dry_run:
            console.print()
            console.print(f"[green]Successfully applied {len(records)} migration(s):[/green]")
            for r in records:
                console.print(f"  • [cyan]{r.version}[/cyan] - {r.name} ({r.execution_time_ms}ms)")

    except Exception as e:
        console.print(f"[red]Error: Migration failed: {e}[/red]")
        raise typer.Exit(1)


@migrate_app.command("down")
def down(
    target: Annotated[
        Optional[int],
        typer.Option("--target", "-t", help="Target version to rollback to"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be done without rolling back"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
):
    """Rollback migrations."""

    if not force and not dry_run:
        confirm = typer.confirm(
            "Are you sure you want to rollback migrations? This may cause data loss."
        )
        if not confirm:
            console.print("[yellow]Rollback cancelled.[/yellow]")
            raise typer.Exit(0)

    async def _down():
        runner = get_runner()
        await runner.initialize()
        return await runner.migrate_down(target_version=target, dry_run=dry_run)

    try:
        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
            console.print()

        records = asyncio.get_event_loop().run_until_complete(_down())

        if not records and not dry_run:
            console.print("[yellow]No migrations to rollback.[/yellow]")
            return

        if not dry_run:
            console.print()
            console.print(f"[green]Successfully rolled back {len(records)} migration(s):[/green]")
            for r in records:
                console.print(f"  • [cyan]{r.version}[/cyan] - {r.name}")

    except Exception as e:
        console.print(f"[red]Error: Rollback failed: {e}[/red]")
        raise typer.Exit(1)


@migrate_app.command("create")
def create(
    name: Annotated[str, typer.Argument(help="Name for the migration (use_underscores)")],
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Description of the migration"),
    ] = None,
):
    """Create a new migration file."""

    # Validate name
    if not name.replace("_", "").isalnum():
        console.print("[red]Error: Migration name must be alphanumeric with underscores only[/red]")
        raise typer.Exit(1)

    # Get next version number
    migrations_dir = Path(__file__).parent.parent.parent / "migrations" / "versions"
    migrations_dir.mkdir(parents=True, exist_ok=True)

    existing = [f for f in os.listdir(migrations_dir) if f.endswith(".py") and not f.startswith("_")]
    versions = []
    for f in existing:
        try:
            versions.append(int(f.split("_")[0]))
        except ValueError:
            pass

    next_version = max(versions, default=0) + 1

    # Create migration file
    filename = f"{next_version:03d}_{name}.py"
    filepath = migrations_dir / filename

    desc = description or f"Migration {next_version}: {name.replace('_', ' ')}"

    template = f'''"""
Migration: {desc}
Created: {datetime.now().strftime('%Y-%m-%d')}

{desc}
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

# Metadata
version = {next_version}
description = "{desc}"


async def up(db: AsyncIOMotorDatabase) -> None:
    """Apply migration."""
    # TODO: Implement migration
    pass


async def down(db: AsyncIOMotorDatabase) -> None:
    """Rollback migration."""
    # TODO: Implement rollback
    pass
'''

    filepath.write_text(template)

    console.print()
    console.print(f"[green]Created migration file:[/green] {filepath}")
    console.print()
    console.print("Edit the file to implement your migration:")
    console.print(f"  [dim]{filepath}[/dim]")


@migrate_app.command("verify")
def verify():
    """Verify migration checksums to detect modified files."""

    async def _verify():
        runner = get_runner()
        await runner.initialize()
        return await runner.verify_checksums()

    try:
        mismatches = asyncio.get_event_loop().run_until_complete(_verify())

        if not mismatches:
            console.print("[green]All migration checksums are valid.[/green]")
            return

        console.print("[red]WARNING: Modified migrations detected![/red]")
        console.print()

        table = Table(title="Checksum Mismatches", show_header=True)
        table.add_column("Version", style="red")
        table.add_column("Name", style="white")
        table.add_column("Status", style="red")

        for m in mismatches:
            table.add_row(str(m["version"]), m["name"], "MODIFIED")

        console.print(table)
        console.print()
        console.print(
            "[yellow]Modifying applied migrations can cause inconsistencies.[/yellow]"
        )

        raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error: Verification failed: {e}[/red]")
        raise typer.Exit(1)
