"""CLI commands for managing monitored groups."""

from typing import Annotated

import typer
from rich.prompt import Prompt

from tg_admin_watch.cli.helpers import (
    build_groups_table,
    confirm,
    console,
    get_repo,
    print_error,
    print_success,
    print_warning,
    require_config,
    run_async,
    select_from_list,
)
from tg_admin_watch.core.models import MonitoredGroup, WatchMode
from tg_admin_watch.infrastructure.telegram.client import TelegramClientManager
from tg_admin_watch.infrastructure.telegram.formatter import MessageFormatter

groups_app = typer.Typer(help="Manage monitored Telegram groups.")
formatter = MessageFormatter()


@groups_app.callback()
def groups_callback() -> None:
    """Ensure configuration is loaded for group commands."""
    require_config()


@groups_app.command("list")
def list_groups() -> None:
    """List all monitored groups."""
    repo = get_repo()
    groups = repo.get_all_groups()
    if not groups:
        print_warning("No monitored groups configured.")
        return
    console.print(build_groups_table(groups))


@groups_app.command("add")
def add_group() -> None:
    """Interactively add a new group to monitor."""
    repo = get_repo()

    async def _add() -> None:
        from tg_admin_watch.config.settings import get_settings

        settings = get_settings()
        manager = TelegramClientManager(settings)

        try:
            await manager.connect()
            dialogs = await manager.get_dialogs()
        finally:
            await manager.disconnect()

        group_dialogs = [d for d in dialogs if d.is_group or d.is_channel]
        if not group_dialogs:
            print_warning("No groups or channels found in your account.")
            return

        items = [f"{d.name} (chat_id: {d.id})" for d in group_dialogs]
        idx = select_from_list(items, prompt="Select a group to monitor")
        if idx is None:
            return

        dialog = group_dialogs[idx]
        chat_id = dialog.id

        existing = repo.get_group_by_chat_id(chat_id)
        if existing:
            print_error(f"Group already monitored: {existing.title}")
            return

        mode_items = [m.value for m in WatchMode]
        mode_idx = select_from_list(mode_items, prompt="Select watch mode")
        if mode_idx is None:
            return

        group = MonitoredGroup(
            chat_id=chat_id,
            title=dialog.name or "",
            enabled=True,
            watch_mode=WatchMode(mode_items[mode_idx]),
        )
        saved = repo.add_group(group)
        print_success(f"Added group '{saved.title}' (chat_id={saved.chat_id}, id={saved.id})")

    run_async(_add())


_DEFAULT_WATCH_MODE = WatchMode.SELECTED_USERS


@groups_app.command("add-by-id")
def add_group_by_id(
    chat_id: int = typer.Argument(..., help="Telegram chat ID"),
    title: str = typer.Option("", help="Display title"),
    watch_mode: Annotated[
        WatchMode,
        typer.Option(help="How to determine which users to watch"),
    ] = _DEFAULT_WATCH_MODE,
) -> None:
    """Add a group by its Telegram chat ID."""
    repo = get_repo()
    if repo.get_group_by_chat_id(chat_id):
        print_error(f"Group with chat_id={chat_id} is already monitored.")
        raise typer.Exit(1)

    group = MonitoredGroup(
        chat_id=chat_id,
        title=title,
        enabled=True,
        watch_mode=watch_mode,
    )
    saved = repo.add_group(group)
    print_success(f"Added group id={saved.id}, chat_id={saved.chat_id}")


@groups_app.command("enable")
def enable_group(
    group_id: int | None = typer.Argument(None, help="Internal group ID"),
) -> None:
    """Enable a monitored group."""
    repo = get_repo()
    if group_id is None:
        group_id = _select_group_id(repo)
        if group_id is None:
            raise typer.Exit(0)

    result = repo.set_group_enabled(group_id, True)
    if result is None:
        print_error(f"Group id={group_id} not found.")
        raise typer.Exit(1)
    print_success(f"Enabled group '{result.title}'")


@groups_app.command("disable")
def disable_group(
    group_id: int | None = typer.Argument(None, help="Internal group ID"),
) -> None:
    """Disable a monitored group."""
    repo = get_repo()
    if group_id is None:
        group_id = _select_group_id(repo)
        if group_id is None:
            raise typer.Exit(0)

    result = repo.set_group_enabled(group_id, False)
    if result is None:
        print_error(f"Group id={group_id} not found.")
        raise typer.Exit(1)
    print_success(f"Disabled group '{result.title}'")


@groups_app.command("edit")
def edit_group(
    group_id: int | None = typer.Argument(None, help="Internal group ID"),
) -> None:
    """Interactively edit a monitored group."""
    repo = get_repo()
    if group_id is None:
        group_id = _select_group_id(repo)
        if group_id is None:
            raise typer.Exit(0)

    group = repo.get_group_by_id(group_id)
    if group is None:
        print_error(f"Group id={group_id} not found.")
        raise typer.Exit(1)

    console.print(f"\nEditing group: [bold]{group.title}[/bold] (id={group.id})")

    new_title = Prompt.ask("Title", default=group.title)
    group.title = new_title

    mode_items = [m.value for m in WatchMode]
    current_idx = mode_items.index(group.watch_mode.value)
    console.print("Watch modes:")
    for i, m in enumerate(mode_items, 1):
        marker = " [green]← current[/green]" if i - 1 == current_idx else ""
        console.print(f"  {i}. {m}{marker}")
    mode_raw = Prompt.ask("Watch mode (number, Enter to keep)", default="")
    if mode_raw.strip():
        try:
            group.watch_mode = WatchMode(mode_items[int(mode_raw) - 1])
        except (ValueError, IndexError):
            print_warning("Invalid mode, keeping current.")

    dest_raw = Prompt.ask(
        "Destination chat ID (Enter to keep, 'none' to clear)",
        default=str(group.destination_chat_id or ""),
    )
    if dest_raw.strip().lower() == "none":
        group.destination_chat_id = None
    elif dest_raw.strip():
        try:
            group.destination_chat_id = int(dest_raw)
        except ValueError:
            print_warning("Invalid chat ID, keeping current.")

    repo.update_group(group)
    print_success(f"Updated group '{group.title}'")


@groups_app.command("remove")
def remove_group(
    group_id: int | None = typer.Argument(None, help="Internal group ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a monitored group and its watched users."""
    repo = get_repo()
    if group_id is None:
        group_id = _select_group_id(repo)
        if group_id is None:
            raise typer.Exit(0)

    group = repo.get_group_by_id(group_id)
    if group is None:
        print_error(f"Group id={group_id} not found.")
        raise typer.Exit(1)

    if not force and not confirm(f"Remove group '{group.title}' and all its watched users?"):
        raise typer.Exit(0)

    repo.delete_group(group_id)
    print_success(f"Removed group '{group.title}'")


def _select_group_id(repo: object) -> int | None:
    """Interactively select a group and return its internal ID."""
    from tg_admin_watch.infrastructure.database.repository import DatabaseRepository

    assert isinstance(repo, DatabaseRepository)
    groups = repo.get_all_groups()
    if not groups:
        print_warning("No groups configured.")
        return None

    items = [f"{g.title} (id={g.id}, chat_id={g.chat_id})" for g in groups]
    idx = select_from_list(items, prompt="Select group")
    if idx is None:
        return None
    return groups[idx].id
