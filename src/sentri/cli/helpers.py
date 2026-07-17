"""Shared CLI helpers and Rich UI utilities."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sentri.config.settings import Settings, get_settings
from sentri.infrastructure.database.repository import DatabaseRepository

console = Console()
err_console = Console(stderr=True)


def get_repo() -> DatabaseRepository:
    """Return a database repository using current settings."""
    settings = get_settings()
    return DatabaseRepository(settings.resolved_db_path)


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from synchronous CLI code."""
    return asyncio.run(coro)


def print_banner() -> None:
    """Print the application banner."""
    console.print(
        Panel.fit(
            "[bold cyan]Sentri[/bold cyan]\n"
            "[dim]Telegram group sentry · forward selected users[/dim]",
            border_style="cyan",
        )
    )


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    err_console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]![/bold yellow] {message}")


def confirm(prompt: str, *, default: bool = False) -> bool:
    """Prompt the user for yes/no confirmation."""
    suffix = " [Y/n]" if default else " [y/N]"
    response = console.input(f"[bold]{prompt}{suffix}:[/bold] ").strip().lower()
    if not response:
        return default
    return response in ("y", "yes")


def select_from_list(
    items: list[str],
    *,
    prompt: str = "Select",
    allow_cancel: bool = True,
) -> int | None:
    """Display a numbered list and return the selected index."""
    if not items:
        print_warning("No items to select.")
        return None

    for i, item in enumerate(items, 1):
        console.print(f"  [cyan]{i}[/cyan]. {item}")

    if allow_cancel:
        console.print("  [dim]0. Cancel[/dim]")

    while True:
        raw = console.input(f"\n[bold]{prompt} (number):[/bold] ").strip()
        if allow_cancel and raw == "0":
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return idx
        except ValueError:
            pass
        print_error("Invalid selection. Try again.")


def format_user_display(user_id: int, display_name: str, username: str | None) -> str:
    """Format a user for CLI display (ID is always shown)."""
    parts = [display_name or "Unknown"]
    if username:
        parts.append(f"@{username}")
    parts.append(f"id:{user_id}")
    return " · ".join(parts)


def build_groups_table(groups: list[Any]) -> Table:
    """Build a Rich table of monitored groups."""
    table = Table(title="Monitored Groups", show_lines=True)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Chat ID", justify="right")
    table.add_column("Title")
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Users", justify="right")

    repo = get_repo()
    for g in groups:
        status = "[green]enabled[/green]" if g.enabled else "[red]disabled[/red]"
        user_count = len(repo.get_users_for_group(g.id)) if g.id else 0
        table.add_row(
            str(g.id),
            str(g.chat_id),
            g.title or "(unnamed)",
            g.watch_mode.value,
            status,
            str(user_count),
        )
    return table


def build_users_table(users: list[Any]) -> Table:
    """Build a Rich table of watched users."""
    table = Table(title="Watched Users", show_lines=True)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("User ID", justify="right", style="bold")
    table.add_column("Display Name")
    table.add_column("Username")
    table.add_column("Admin")
    table.add_column("Status")

    for u in users:
        status = "[green]enabled[/green]" if u.enabled else "[red]disabled[/red]"
        admin = "[cyan]yes[/cyan]" if u.is_admin else "no"
        table.add_row(
            str(u.id),
            str(u.user_id),
            u.display_name or "—",
            f"@{u.username}" if u.username else "—",
            admin,
            status,
        )
    return table


def init_app_context() -> Settings:
    """Initialize settings and logging for CLI commands."""
    from sentri.utils.logging import setup_logging

    settings = get_settings()
    setup_logging(
        level=settings.log_level,
        log_file=settings.resolved_log_file,
    )
    return settings


def require_config() -> None:
    """Initialize app context or exit with a configuration error."""
    try:
        init_app_context()
    except Exception as exc:
        print_error(
            f"{exc}\nCopy .env.example to .env and set TELEGRAM_API_ID and TELEGRAM_API_HASH."
        )
        raise SystemExit(1) from exc
