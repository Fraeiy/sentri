"""FastAPI dependencies for the web application."""


from fastapi import Depends, HTTPException, Request

from sentri.config.settings import Settings, get_settings
from sentri.infrastructure.database.repository import DatabaseRepository
from sentri.utils.logging import setup_logging


def init_web_context() -> Settings:
    """Initialize logging and return settings."""
    settings = get_settings()
    setup_logging(level=settings.log_level, log_file=settings.resolved_log_file)
    return settings


def get_repository(settings: Settings = Depends(init_web_context)) -> DatabaseRepository:
    """Return a database repository instance."""
    return DatabaseRepository(settings.resolved_db_path)


async def verify_web_token(
    request: Request,
    settings: Settings = Depends(init_web_context),
) -> None:
    """Optional bearer token check when ``web_token`` is configured."""
    if not settings.web_token:
        return

    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {settings.web_token}":
        return

    token = request.query_params.get("token")
    if token == settings.web_token:
        return

    raise HTTPException(status_code=401, detail="Invalid or missing web token")
