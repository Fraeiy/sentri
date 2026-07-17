"""Base classes for notification backends.

Future backends (Discord, Slack, Email, ntfy, webhooks) should extend
``BaseNotificationBackend`` and register themselves in the notification registry.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseNotificationBackend(ABC):
    """Abstract base for all notification delivery backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier."""
        ...

    @abstractmethod
    async def send_text(self, text: str, *, destination: int | str) -> int | str:
        """Deliver a plain-text notification."""
        ...

    @abstractmethod
    async def send_media(
        self,
        media: Any,
        *,
        caption: str | None,
        destination: int | str,
    ) -> int | str:
        """Deliver a media notification with optional caption."""
        ...

    async def close(self) -> None:
        """Release resources. Override if cleanup is needed."""
        return None


class NotificationRegistry:
    """Registry for available notification backends.

    Example future usage::

        registry.register("discord", DiscordBackend)
        registry.register("slack", SlackBackend)
        backend = registry.create("telegram", client=telethon_client)
    """

    def __init__(self) -> None:
        self._backends: dict[str, type[BaseNotificationBackend]] = {}

    def register(self, name: str, backend_cls: type[BaseNotificationBackend]) -> None:
        """Register a backend class by name."""
        self._backends[name] = backend_cls

    def create(self, name: str, **kwargs: Any) -> BaseNotificationBackend:
        """Instantiate a registered backend."""
        if name not in self._backends:
            available = ", ".join(sorted(self._backends)) or "(none)"
            raise ValueError(f"Unknown backend '{name}'. Available: {available}")
        return self._backends[name](**kwargs)

    def list_backends(self) -> list[str]:
        """Return names of all registered backends."""
        return sorted(self._backends.keys())


# Global registry instance for future extensibility
notification_registry = NotificationRegistry()
