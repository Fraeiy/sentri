"""Main Typer CLI application."""

import sys

import typer
from rich.prompt import Prompt

from tg_admin_watch import __version__
from tg_admin_watch.cli import groups, users
from tg_admin_watch.cli.helpers import (
    console,
    get_repo,
    print_banner,
    print_error,
    print_success,
    print_warning,
    require_config,
    run_async,
    select_from_list,
)
from tg_admin_watch.core.services.monitor_service import MonitorService
from tg_admin_watch.infrastructure.telegram.client import TelegramClientManager

app = typer.Typer(
    name="tg-admin-watch",
    help="Monitor Telegram groups and forward messages from selected users.",
    no_args_is_help=True,
    pretty_exceptions_enable=True,
)

config_app = typer.Typer(help="Application configuration.")
app.add_typer(groups.groups_app, name="groups")
app.add_typer(users.users_app, name="users")
app.add_typer(config_app, name="config")


@app.command()
def version() -> None:
    """Show the application version."""
    console.print(f"tg-admin-watch v{__version__}")


@app.command()
def auth() -> None:
    """Authenticate with your personal Telegram account."""
    require_config()
    print_banner()

    from tg_admin_watch.config.settings import get_settings

    settings = get_settings()
    manager = TelegramClientManager(settings)

    def phone_callback() -> str:
        return Prompt.ask("[bold]Phone number[/bold] (with country code, e.g. +1234567890)")

    def code_callback() -> str:
        return Prompt.ask("[bold]Verification code[/bold]")

    def password_callback() -> str:
        return Prompt.ask("[bold]2FA password[/bold]", password=True)

    async def _auth() -> None:
        try:
            await manager.authenticate_interactive(
                phone_callback=phone_callback,
                code_callback=code_callback,
                password_callback=password_callback,
            )
            print_success("Authentication successful!")
            print_success(f"Session saved to: {settings.resolved_session_path}.session")
        except Exception as exc:
            print_error(f"Authentication failed: {exc}")
            raise typer.Exit(1) from exc
        finally:
            await manager.disconnect()

    run_async(_auth())


@app.command()
def status() -> None:
    """Show current configuration status."""
    require_config()
    print_banner()
    from tg_admin_watch.config.settings import get_settings

    settings = get_settings()
    repo = get_repo()
    app_settings = repo.get_app_settings()
    groups_list = repo.get_all_groups()
    enabled_groups = [g for g in groups_list if g.enabled]

    session_exists = TelegramClientManager.session_exists(settings.resolved_session_path)

    console.print("\n[bold]Configuration[/bold]")
    console.print(f"  Database:    {settings.resolved_db_path}")
    console.print(f"  Session:     {settings.resolved_session_path}.session")
    console.print(f"  Authenticated: {'[green]yes[/green]' if session_exists else '[red]no[/red]'}")
    console.print(
        f"  Destination: {app_settings.destination_title or 'not set'}"
        f" (chat_id={app_settings.destination_chat_id or 'none'})"
    )
    console.print(f"  Groups:      {len(enabled_groups)} enabled / {len(groups_list)} total")

    total_users = sum(
        len(repo.get_users_for_group(g.id))  # type: ignore[arg-type]
        for g in groups_list
        if g.id is not None
    )
    console.print(f"  Watched users: {total_users}")


@app.command()
def watch() -> None:
    """Start monitoring and forwarding messages."""
    require_config()
    print_banner()

    from tg_admin_watch.config.settings import get_settings

    settings = get_settings()

    if not TelegramClientManager.session_exists(settings.resolved_session_path):
        print_error("Not authenticated. Run 'tg-admin-watch auth' first.")
        raise typer.Exit(1)

    repo = get_repo()
    enabled = repo.get_all_groups(enabled_only=True)
    if not enabled:
        print_error("No enabled groups. Add groups with 'tg-admin-watch groups add'.")
        raise typer.Exit(1)

    app_settings = repo.get_app_settings()
    has_destination = app_settings.destination_chat_id is not None or any(
        g.destination_chat_id for g in enabled
    )
    if not has_destination:
        print_error(
            "No destination configured. Run 'tg-admin-watch config set-destination' "
            "or set per-group destinations."
        )
        raise typer.Exit(1)

    async def _watch() -> None:
        manager = TelegramClientManager(settings)
        service = MonitorService(settings, repo, manager)
        try:
            await service.start()
        except KeyboardInterrupt:
            console.print("\n[dim]Shutting down...[/dim]")
        finally:
            await manager.disconnect()

    try:
        run_async(_watch())
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
        sys.exit(0)


@config_app.command("set-destination")
def set_destination() -> None:
    """Interactively set the global forward destination chat."""
    require_config()

    async def _set() -> None:
        from tg_admin_watch.config.settings import get_settings

        settings = get_settings()
        manager = TelegramClientManager(settings)

        try:
            await manager.connect()
            dialogs = await manager.get_dialogs()
        finally:
            await manager.disconnect()

        if not dialogs:
            print_warning("No dialogs found.")
            return

        items = [f"{d.name} (chat_id: {d.id})" for d in dialogs]
        idx = select_from_list(items, prompt="Select destination chat")
        if idx is None:
            return

        dialog = dialogs[idx]
        repo = get_repo()
        repo.set_destination_chat(dialog.id, dialog.name or "")
        print_success(f"Destination set to '{dialog.name}' (chat_id={dialog.id})")

    run_async(_set())


@config_app.command("set-destination-id")
def set_destination_by_id(
    chat_id: int = typer.Argument(..., help="Destination Telegram chat ID"),
    title: str = typer.Option("", help="Display title"),
) -> None:
    """Set the global forward destination by chat ID."""
    require_config()
    repo = get_repo()
    repo.set_destination_chat(chat_id, title)
    print_success(f"Destination set to chat_id={chat_id}")


@config_app.command("show")
def show_config() -> None:
    """Show all stored configuration."""
    require_config()
    repo = get_repo()
    app_settings = repo.get_app_settings()
    console.print("\n[bold]App Settings[/bold]")
    console.print(f"  destination_chat_id: {app_settings.destination_chat_id}")
    console.print(f"  destination_title:   {app_settings.destination_title}")

    groups_list = repo.get_all_groups()
    if groups_list:
        from tg_admin_watch.cli.helpers import build_groups_table

        console.print(build_groups_table(groups_list))


@app.command()
def interactive() -> None:
    """Launch the interactive configuration menu."""
    require_config()
    print_banner()

    menu_items = [
        "Show status",
        "Authenticate",
        "Manage groups",
        "Manage users",
        "Set destination",
        "Start watching",
        "Exit",
    ]

    sub_menus = {
        "Manage groups": [
            ("List groups", groups.list_groups),
            ("Add group", groups.add_group),
            ("Edit group", groups.edit_group),
            ("Enable group", groups.enable_group),
            ("Disable group", groups.disable_group),
            ("Remove group", groups.remove_group),
        ],
        "Manage users": [
            ("List users", users.list_users),
            ("Add user", users.add_user),
            ("Sync admins", users.sync_admins),
            ("Remove user", users.remove_user),
        ],
    }

    while True:
        console.print()
        idx = select_from_list(menu_items, prompt="Main menu", allow_cancel=False)
        if idx is None or idx == len(menu_items) - 1:
            console.print("[dim]Goodbye![/dim]")
            break

        choice = menu_items[idx]

        if choice == "Show status":
            status()
        elif choice == "Authenticate":
            auth()
        elif choice == "Set destination":
            set_destination()
        elif choice == "Start watching":
            watch()
            break
        elif choice in sub_menus:
            _run_sub_menu(sub_menus[choice])
        console.print()


def _run_sub_menu(items: list[tuple[str, object]]) -> None:
    """Run a sub-menu loop."""
    labels = [label for label, _ in items]
    while True:
        idx = select_from_list(labels + ["Back"], prompt="Sub-menu")
        if idx is None or idx == len(labels):
            break
        _, command = items[idx]
        try:
            command()  # type: ignore[operator]
        except typer.Exit:
            pass
        except Exception as exc:
            print_error(str(exc))


if __name__ == "__main__":
    app()
