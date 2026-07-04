"""Tests for notification backend registry."""

from tg_admin_watch.infrastructure.notifications.base import (
    NotificationRegistry,
    notification_registry,
)


class TestNotificationRegistry:
    """Tests for the extensible notification backend registry."""

    def test_telegram_backend_registered(self) -> None:
        assert "telegram" in notification_registry.list_backends()

    def test_create_unknown_backend_raises(self) -> None:
        registry = NotificationRegistry()
        try:
            registry.create("nonexistent")
            raise AssertionError("Expected ValueError")
        except ValueError as exc:
            assert "nonexistent" in str(exc)

    def test_register_custom_backend(self) -> None:
        class DummyBackend:
            name = "dummy"

            async def send_text(self, text: str, *, destination: int | str) -> int | str:
                return 1

            async def send_media(
                self, media: object, *, caption: str | None, destination: int | str
            ) -> int | str:
                return 1

        registry = NotificationRegistry()

        class ConcreteBackend(DummyBackend):
            pass

        from tg_admin_watch.infrastructure.notifications.base import BaseNotificationBackend

        # Register a minimal concrete backend
        class MinimalBackend(BaseNotificationBackend):
            @property
            def name(self) -> str:
                return "minimal"

            async def send_text(self, text: str, *, destination: int | str) -> int | str:
                return 0

            async def send_media(
                self, media: object, *, caption: str | None, destination: int | str
            ) -> int | str:
                return 0

        registry.register("minimal", MinimalBackend)
        backend = registry.create("minimal")
        assert backend.name == "minimal"
