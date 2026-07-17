"""CLI commands for managing watched users."""

import typer

from sentri.cli.helpers import (
    build_users_table,
    confirm,
    console,
    format_user_display,
    get_repo,
    print_error,
    print_success,
    print_warning,
    require_config,
    run_async,
    select_from_list,
)
from sentri.core.models import WatchedUser
from sentri.infrastructure.telegram.client import TelegramClientManager
from sentri.infrastructure.telegram.formatter import MessageFormatter

users_app = typer.Typer(help="Manage watched users within monitored groups.")
formatter = MessageFormatter()


@users_app.callback()
def users_callback() -> None:
    """Ensure configuration is loaded for user commands."""
    require_config()


@users_app.command("list")
def list_users(
    group_id: int | None = typer.Argument(None, help="Internal group ID"),
) -> None:
    """List watched users for a group."""
    repo = get_repo()
    if group_id is None:
        group_id = _select_group_id()
        if group_id is None:
            raise typer.Exit(0)

    users = repo.get_users_for_group(group_id)
    if not users:
        print_warning("No watched users for this group.")
        return
    console.print(build_users_table(users))


@users_app.command("add")
def add_user(
    group_id: int | None = typer.Argument(None, help="Internal group ID"),
) -> None:
    """Interactively add a user to watch (matched by user ID)."""
    repo = get_repo()
    if group_id is None:
        group_id = _select_group_id()
        if group_id is None:
            raise typer.Exit(0)

    group = repo.get_group_by_id(group_id)
    if group is None:
        print_error(f"Group id={group_id} not found.")
        raise typer.Exit(1)

    async def _add() -> None:
        from sentri.config.settings import get_settings

        settings = get_settings()
        manager = TelegramClientManager(settings)

        try:
            await manager.connect()
            participants = await manager.client.get_participants(group.chat_id)
        finally:
            await manager.disconnect()

        if not participants:
            print_warning("No participants found in this group.")
            return

        items = []
        for p in participants:
            info = formatter.user_info_from_telethon(p)
            items.append(format_user_display(info.user_id, info.display_name, info.username))

        idx = select_from_list(items, prompt="Select user to watch")
        if idx is None:
            return

        participant = participants[idx]
        info = formatter.user_info_from_telethon(participant)

        existing = repo.get_user_by_telegram_id(group_id, info.user_id)
        if existing:
            display = format_user_display(info.user_id, info.display_name, info.username)
            print_error(f"User already watched: {display}")
            return

        user = WatchedUser(
            group_id=group_id,
            user_id=info.user_id,
            display_name=info.display_name,
            username=info.username,
            enabled=True,
        )
        saved = repo.add_user(user)
        print_success(
            f"Added user {format_user_display(saved.user_id, saved.display_name, saved.username)}"
        )

    run_async(_add())


@users_app.command("add-by-id")
def add_user_by_id(
    group_id: int = typer.Argument(..., help="Internal group ID"),
    user_id: int = typer.Argument(..., help="Immutable Telegram user ID"),
    display_name: str = typer.Option("", help="Display name for CLI"),
    username: str = typer.Option(None, help="Username snapshot for CLI"),
) -> None:
    """Add a user by their Telegram user ID."""
    repo = get_repo()
    group = repo.get_group_by_id(group_id)
    if group is None:
        print_error(f"Group id={group_id} not found.")
        raise typer.Exit(1)

    existing = repo.get_user_by_telegram_id(group_id, user_id)
    if existing:
        print_error(f"User id:{user_id} already watched in this group.")
        raise typer.Exit(1)

    user = WatchedUser(
        group_id=group_id,
        user_id=user_id,
        display_name=display_name or f"User (id:{user_id})",
        username=username,
        enabled=True,
    )
    saved = repo.add_user(user)
    print_success(f"Added user id:{saved.user_id} to group id={group_id}")


@users_app.command("sync-admins")
def sync_admins(
    group_id: int | None = typer.Argument(None, help="Internal group ID"),
) -> None:
    """Discover and sync admin users from Telegram (stored by user ID)."""
    repo = get_repo()
    if group_id is None:
        group_id = _select_group_id()
        if group_id is None:
            raise typer.Exit(0)

    group = repo.get_group_by_id(group_id)
    if group is None:
        print_error(f"Group id={group_id} not found.")
        raise typer.Exit(1)

    async def _sync() -> None:
        from sentri.config.settings import get_settings

        settings = get_settings()
        manager = TelegramClientManager(settings)

        try:
            await manager.connect()
            admins = await manager.get_chat_admins(group.chat_id)
        finally:
            await manager.disconnect()

        admin_users = []
        for admin in admins:
            info = formatter.user_info_from_telethon(admin)
            admin_users.append(
                WatchedUser(
                    group_id=group_id,
                    user_id=info.user_id,
                    display_name=info.display_name,
                    username=info.username,
                    is_admin=True,
                    enabled=True,
                )
            )

        count = repo.upsert_admin_users(group_id, admin_users)
        print_success(f"Synced {count} admin(s) for group '{group.title}'")

    run_async(_sync())


@users_app.command("remove")
def remove_user(
    user_record_id: int | None = typer.Argument(None, help="Internal user record ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a watched user."""
    repo = get_repo()
    if user_record_id is None:
        user_record_id = _select_user_id()
        if user_record_id is None:
            raise typer.Exit(0)

    user = repo.get_user_by_id(user_record_id)
    if user is None:
        print_error(f"User record id={user_record_id} not found.")
        raise typer.Exit(1)

    if not force and not confirm(
        f"Remove user {format_user_display(user.user_id, user.display_name, user.username)}?"
    ):
        raise typer.Exit(0)

    repo.delete_user(user_record_id)
    print_success(f"Removed user id:{user.user_id}")


@users_app.command("enable")
def enable_user(
    user_record_id: int = typer.Argument(..., help="Internal user record ID"),
) -> None:
    """Enable a watched user."""
    repo = get_repo()
    user = repo.get_user_by_id(user_record_id)
    if user is None:
        print_error(f"User record id={user_record_id} not found.")
        raise typer.Exit(1)
    user.enabled = True
    repo.update_user(user)
    print_success(f"Enabled user id:{user.user_id}")


@users_app.command("disable")
def disable_user(
    user_record_id: int = typer.Argument(..., help="Internal user record ID"),
) -> None:
    """Disable a watched user."""
    repo = get_repo()
    user = repo.get_user_by_id(user_record_id)
    if user is None:
        print_error(f"User record id={user_record_id} not found.")
        raise typer.Exit(1)
    user.enabled = False
    repo.update_user(user)
    print_success(f"Disabled user id:{user.user_id}")


def _select_group_id() -> int | None:
    """Interactively select a group."""
    repo = get_repo()
    groups = repo.get_all_groups()
    if not groups:
        print_warning("No groups configured. Add a group first.")
        return None
    items = [f"{g.title} (id={g.id})" for g in groups]
    idx = select_from_list(items, prompt="Select group")
    if idx is None:
        return None
    return groups[idx].id


def _select_user_id() -> int | None:
    """Interactively select a user across all groups."""
    repo = get_repo()
    group_id = _select_group_id()
    if group_id is None:
        return None

    users = repo.get_users_for_group(group_id)
    if not users:
        print_warning("No users in this group.")
        return None

    items = [format_user_display(u.user_id, u.display_name, u.username) for u in users]
    idx = select_from_list(items, prompt="Select user")
    if idx is None:
        return None
    return users[idx].id
