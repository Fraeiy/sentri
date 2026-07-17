"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sentri import __version__
from sentri.web.routes import api, pages


def create_app() -> FastAPI:
    """Create and configure the FastAPI web application."""
    app = FastAPI(
        title="Sentri",
        description="Web dashboard for monitoring Telegram groups",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")

    return app
