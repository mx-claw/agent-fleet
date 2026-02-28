from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from .config import AppConfig


@click.command()
@click.option("--database", "database_path", default="agent_fleet.db", show_default=True)
def main(database_path: str) -> None:
    """Placeholder CLI for the repository foundation step."""
    config = AppConfig.from_paths(database_path=database_path)
    console = Console()

    table = Table(title="agent-fleet")
    table.add_column("Layer")
    table.add_column("Status")
    table.add_row("Config", "ready")
    table.add_row("Persistence", str(config.database_path))
    table.add_row("Queue", "FIFO core available")
    table.add_row("Orchestrator", "not implemented")

    console.print(table)
