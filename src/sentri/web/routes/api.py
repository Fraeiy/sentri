"""JSON and HTMX API routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from sentri.config.settings import Settings
from sentri.core.models import MonitoredGroup, WatchedUser
from sentri.infrastructure.database.repository import DatabaseRepository
from sentri.infrastructure.telegram.client import TelegramClientManager
from sentri.infrastructure.telegram.formatter import MessageFormatter
from sentri.web.auth_flow import WebAuthFlow
from sentri.web.dependencies import get_repository, init_web_context, verify_web_token
from sentri.web.schemas import (
    AuthCodeRequest,
    AuthPasswordRequest,
    AuthPhoneRequest,
    DestinationSet,
    GroupCreate,
    GroupUpdate,
    UserCreate,
)
from sentri.web.watch_manager import WatchManager

router = APIRouter(dependencies=[Depends(verify_web_token)])
formatter = MessageFormatter()


def _group_dict(group: MonitoredGroup, repo: DatabaseRepository) -> dict[str, Any]:
    return {
        "id": group.id,
        "chat_id": group.chat_id,
        "title": group.title,
        "enabled": group.enabled,
        "watch_mode": group.watch_mode.value,
        "destination_chat_id": group.destination_chat_id,
        "user_count": len(repo.get_users_for_group(group.id)) if group.id else 0,
    }


def _user_dict(user: WatchedUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "group_id": user.group_id,
        "user_id": user.user_id,
        "display_name": user.display_name,
        "username": user.username,
        "is_admin": user.is_admin,
        "enabled": user.enabled,
    }


@router.get("/status")
async def api_status(
    settings: Settings = Depends(init_web_context),
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Return application status summary."""
    app_settings = repo.get_app_settings()
    groups = repo.get_all_groups()
    enabled = [g for g in groups if g.enabled]
    total_users = sum(
        len(repo.get_users_for_group(g.id))  # type: ignore[arg-type]
        for g in groups
        if g.id is not None
    )
    watch = WatchManager.get_instance().status
    return {
        "authenticated": TelegramClientManager.session_exists(settings.resolved_session_path),
        "destination_chat_id": app_settings.destination_chat_id,
        "destination_title": app_settings.destination_title,
        "groups_total": len(groups),
        "groups_enabled": len(enabled),
        "watched_users": total_users,
        "watch_running": watch.running,
        "watch_started_at": watch.started_at.isoformat() if watch.started_at else None,
        "watch_error": watch.last_error,
    }


@router.get("/groups")
async def api_list_groups(
    repo: DatabaseRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    """List all monitored groups."""
    return [_group_dict(g, repo) for g in repo.get_all_groups()]


@router.post("/groups")
async def api_add_group(
    body: GroupCreate,
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Add a monitored group by chat ID."""
    if repo.get_group_by_chat_id(body.chat_id):
        raise HTTPException(status_code=409, detail="Group already monitored")
    group = MonitoredGroup(
        chat_id=body.chat_id,
        title=body.title,
        watch_mode=body.watch_mode,
        enabled=True,
    )
    saved = repo.add_group(group)
    return _group_dict(saved, repo)


@router.patch("/groups/{group_id}")
async def api_update_group(
    group_id: int,
    body: GroupUpdate,
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Update a monitored group."""
    group = repo.get_group_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    if body.title is not None:
        group.title = body.title
    if body.watch_mode is not None:
        group.watch_mode = body.watch_mode
    if body.destination_chat_id is not None:
        group.destination_chat_id = body.destination_chat_id
    if body.enabled is not None:
        group.enabled = body.enabled
    updated = repo.update_group(group)
    return _group_dict(updated, repo)


@router.delete("/groups/{group_id}")
async def api_delete_group(
    group_id: int,
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, str]:
    """Delete a monitored group."""
    if not repo.delete_group(group_id):
        raise HTTPException(status_code=404, detail="Group not found")
    return {"status": "deleted"}


@router.get("/groups/{group_id}/users")
async def api_list_users(
    group_id: int,
    repo: DatabaseRepository = Depends(get_repository),
) -> list[dict[str, Any]]:
    """List watched users for a group."""
    if repo.get_group_by_id(group_id) is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return [_user_dict(u) for u in repo.get_users_for_group(group_id)]


@router.post("/groups/{group_id}/users")
async def api_add_user(
    group_id: int,
    body: UserCreate,
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Add a watched user by Telegram user ID."""
    if repo.get_group_by_id(group_id) is None:
        raise HTTPException(status_code=404, detail="Group not found")
    if repo.get_user_by_telegram_id(group_id, body.user_id):
        raise HTTPException(status_code=409, detail="User already watched")
    user = WatchedUser(
        group_id=group_id,
        user_id=body.user_id,
        display_name=body.display_name or f"User (id:{body.user_id})",
        username=body.username,
        enabled=True,
    )
    saved = repo.add_user(user)
    return _user_dict(saved)


@router.delete("/users/{user_record_id}")
async def api_delete_user(
    user_record_id: int,
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, str]:
    """Remove a watched user."""
    if not repo.delete_user(user_record_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}


@router.post("/groups/{group_id}/sync-admins")
async def api_sync_admins(
    group_id: int,
    settings: Settings = Depends(init_web_context),
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Discover and sync admin users from Telegram."""
    group = repo.get_group_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

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
    return {"synced": count}


@router.get("/telegram/dialogs")
async def api_telegram_dialogs(
    settings: Settings = Depends(init_web_context),
) -> list[dict[str, Any]]:
    """List Telegram dialogs for group/destination picker."""
    manager = TelegramClientManager(settings)
    try:
        await manager.connect()
        dialogs = await manager.get_dialogs()
    finally:
        await manager.disconnect()

    return [
        {
            "id": d.id,
            "name": d.name or "(unnamed)",
            "is_group": d.is_group,
            "is_channel": d.is_channel,
            "is_user": d.is_user,
        }
        for d in dialogs
    ]


@router.get("/telegram/groups")
async def api_telegram_groups(
    settings: Settings = Depends(init_web_context),
) -> list[dict[str, Any]]:
    """List group/channel dialogs only."""
    dialogs = await api_telegram_dialogs(settings)
    return [d for d in dialogs if d["is_group"] or d["is_channel"]]


@router.get("/telegram/participants/{chat_id}")
async def api_telegram_participants(
    chat_id: int,
    settings: Settings = Depends(init_web_context),
) -> list[dict[str, Any]]:
    """List participants in a chat for user picker."""
    manager = TelegramClientManager(settings)
    try:
        await manager.connect()
        participants = await manager.client.get_participants(chat_id)
    finally:
        await manager.disconnect()

    result = []
    for p in participants:
        info = formatter.user_info_from_telethon(p)
        result.append(
            {
                "user_id": info.user_id,
                "display_name": info.display_name,
                "username": info.username,
            }
        )
    return result


@router.post("/config/destination")
async def api_set_destination(
    body: DestinationSet,
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Set the global forward destination."""
    repo.set_destination_chat(body.chat_id, body.title)
    settings = repo.get_app_settings()
    return {
        "destination_chat_id": settings.destination_chat_id,
        "destination_title": settings.destination_title,
    }


@router.post("/watch/start")
async def api_watch_start(
    settings: Settings = Depends(init_web_context),
    repo: DatabaseRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Start background monitoring."""
    if not TelegramClientManager.session_exists(settings.resolved_session_path):
        raise HTTPException(
            status_code=400,
            detail="Not authenticated. Complete Telegram login first.",
        )
    if not repo.get_all_groups(enabled_only=True):
        raise HTTPException(status_code=400, detail="No enabled groups configured.")
    app_settings = repo.get_app_settings()
    has_dest = app_settings.destination_chat_id is not None or any(
        g.destination_chat_id for g in repo.get_all_groups(enabled_only=True)
    )
    if not has_dest:
        raise HTTPException(status_code=400, detail="No destination chat configured.")

    manager = WatchManager.get_instance()
    await manager.start(settings, repo)
    status = manager.status
    return {"running": status.running, "started_at": status.started_at}


@router.post("/watch/stop")
async def api_watch_stop() -> dict[str, bool]:
    """Stop background monitoring."""
    manager = WatchManager.get_instance()
    await manager.stop()
    return {"running": False}


@router.post("/auth/phone")
async def api_auth_phone(
    body: AuthPhoneRequest,
    settings: Settings = Depends(init_web_context),
) -> dict[str, str]:
    """Send Telegram verification code."""
    flow = WebAuthFlow.get_instance()
    state = await flow.send_code(settings, body.phone.strip())
    if state.error:
        raise HTTPException(status_code=400, detail=state.error)
    return {"step": state.step, "message": state.message}


@router.post("/auth/code")
async def api_auth_code(body: AuthCodeRequest) -> dict[str, str]:
    """Submit Telegram verification code."""
    flow = WebAuthFlow.get_instance()
    state = await flow.submit_code(body.code.strip())
    if state.error:
        raise HTTPException(status_code=400, detail=state.error)
    return {"step": state.step, "message": state.message}


@router.post("/auth/password")
async def api_auth_password(body: AuthPasswordRequest) -> dict[str, str]:
    """Submit Telegram 2FA password."""
    flow = WebAuthFlow.get_instance()
    state = await flow.submit_password(body.password)
    if state.error:
        raise HTTPException(status_code=400, detail=state.error)
    return {"step": state.step, "message": state.message}
