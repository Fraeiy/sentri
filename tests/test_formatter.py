"""Tests for message formatting utilities."""

from datetime import UTC, datetime

from tg_admin_watch.core.models import MonitoredGroup, TelegramUserInfo
from tg_admin_watch.infrastructure.telegram.formatter import MessageFormatter


class TestMessageFormatter:
    """Tests for MessageFormatter."""

    def test_build_user_display_name_with_id(self) -> None:
        name = MessageFormatter.build_user_display_name(
            "Alice",
            "Smith",
            username="alice",
            user_id=12345,
        )
        assert "Alice Smith" in name
        assert "@alice" in name
        assert "id:12345" in name

    def test_build_user_display_name_unknown(self) -> None:
        name = MessageFormatter.build_user_display_name(None, None, user_id=99)
        assert "Unknown" in name
        assert "id:99" in name

    def test_build_forward_header(self) -> None:
        group = MonitoredGroup(chat_id=100, title="Dev Chat")
        sender = TelegramUserInfo(user_id=42, display_name="Bob (id:42)")
        header = MessageFormatter.build_forward_header(
            group=group,
            sender=sender,
            message_date=datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC),
            original_text_preview="Hello world",
        )
        assert "Dev Chat" in header
        assert "Bob" in header
        assert "Hello world" in header
        assert "2026-01-15" in header

    def test_has_media_false(self) -> None:
        class FakeMessage:
            media = None

        assert MessageFormatter.has_media(FakeMessage()) is False

    def test_has_media_true(self) -> None:
        class FakeMessage:
            media = object()

        assert MessageFormatter.has_media(FakeMessage()) is True

    def test_extract_message_text(self) -> None:
        class FakeMessage:
            message = "Hello"

        assert MessageFormatter.extract_message_text(FakeMessage()) == "Hello"
