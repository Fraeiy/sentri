"""Background watch process manager for the web UI."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sentri.config.settings import Settings
from sentri.core.services.monitor_service import MonitorService
from sentri.infrastructure.database.repository import DatabaseRepository
from sentri.infrastructure.telegram.client import TelegramClientManager

logger = logging.getLogger(__name__)


@dataclass
class WatchStatus:
    """Runtime status of the background watcher."""

    running: bool = False
    started_at: datetime | None = None
    last_error: str | None = None
    task_done: bool = False


class WatchManager:
    """Singleton manager for starting and stopping the monitor from the web UI."""

    _instance: "WatchManager | None" = None

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._client_manager: TelegramClientManager | None = None
        self._status = WatchStatus()
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "WatchManager":
        """Return the global watch manager singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def status(self) -> WatchStatus:
        """Return current watch status."""
        if self._task is not None and self._task.done() and self._status.running:
            self._status.running = False
            self._status.task_done = True
            exc = self._task.exception()
            if exc and not self._status.last_error:
                self._status.last_error = str(exc)
        return self._status

    async def start(self, settings: Settings, repository: DatabaseRepository) -> None:
        """Start the background monitor if not already running."""
        async with self._lock:
            if self._status.running and self._task and not self._task.done():
                return

            self._client_manager = TelegramClientManager(settings)
            service = MonitorService(settings, repository, self._client_manager)
            self._task = asyncio.create_task(self._run(service))
            self._status = WatchStatus(
                running=True,
                started_at=datetime.now(UTC),
            )
            logger.info("Web UI started background watch")

    async def stop(self) -> None:
        """Stop the background monitor."""
        async with self._lock:
            if self._client_manager is not None:
                try:
                    await self._client_manager.disconnect()
                except Exception as exc:
                    logger.debug("Disconnect error: %s", exc)

            if self._task is not None and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    self._status.last_error = str(exc)

            self._status.running = False
            self._task = None
            self._client_manager = None
            logger.info("Web UI stopped background watch")

    async def _run(self, service: MonitorService) -> None:
        """Run the monitor service until cancelled or error."""
        try:
            await service.start()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._status.last_error = str(exc)
            self._status.running = False
            logger.exception("Background watch failed")
            raise
        finally:
            self._status.running = False
