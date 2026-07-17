"""HTML page routes."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from sentri import __version__
from sentri.config.settings import Settings
from sentri.infrastructure.database.repository import DatabaseRepository
from sentri.infrastructure.telegram.client import TelegramClientManager
from sentri.web.dependencies import get_repository, init_web_context, verify_web_token
from sentri.web.watch_manager import WatchManager

router = APIRouter(dependencies=[Depends(verify_web_token)])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    settings: Settings = Depends(init_web_context),
    repo: DatabaseRepository = Depends(get_repository),
) -> HTMLResponse:
    """Render the main dashboard."""
    app_settings = repo.get_app_settings()
    groups = repo.get_all_groups()
    watch = WatchManager.get_instance().status
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "version": __version__,
            "authenticated": TelegramClientManager.session_exists(settings.resolved_session_path),
            "destination_title": app_settings.destination_title,
            "destination_chat_id": app_settings.destination_chat_id,
            "groups": groups,
            "groups_enabled": sum(1 for g in groups if g.enabled),
            "watch_running": watch.running,
            "watch_error": watch.last_error,
        },
    )
