"""Tests for the SQLite repository."""

import sqlite3

import pytest

from sentri.core.models import (
    ForwardedMessageRecord,
    MonitoredGroup,
    WatchedUser,
    WatchMode,
)


class TestMonitoredGroups:
    """Tests for monitored group CRUD operations."""

    def test_add_and_get_group(self, repository) -> None:
        group = MonitoredGroup(
            chat_id=-1001234567890,
            title="Test Group",
            enabled=True,
            watch_mode=WatchMode.SELECTED_USERS,
        )
        saved = repository.add_group(group)
        assert saved.id is not None
        assert saved.chat_id == -1001234567890
        assert saved.title == "Test Group"

        fetched = repository.get_group_by_chat_id(-1001234567890)
        assert fetched is not None
        assert fetched.id == saved.id

    def test_get_all_groups_enabled_filter(self, repository) -> None:
        repository.add_group(MonitoredGroup(chat_id=1, title="Enabled", enabled=True))
        repository.add_group(MonitoredGroup(chat_id=2, title="Disabled", enabled=False))

        all_groups = repository.get_all_groups()
        assert len(all_groups) == 2

        enabled = repository.get_all_groups(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].title == "Enabled"

    def test_update_group(self, repository) -> None:
        saved = repository.add_group(MonitoredGroup(chat_id=100, title="Old Title", enabled=True))
        saved.title = "New Title"
        saved.watch_mode = WatchMode.ADMINS_ONLY
        updated = repository.update_group(saved)
        assert updated.title == "New Title"
        assert updated.watch_mode == WatchMode.ADMINS_ONLY

    def test_delete_group_cascades_users(self, repository) -> None:
        group = repository.add_group(MonitoredGroup(chat_id=100, title="G"))
        repository.add_user(WatchedUser(group_id=group.id, user_id=111, display_name="User A"))
        repository.delete_group(group.id)  # type: ignore[arg-type]
        users = repository.get_users_for_group(group.id)  # type: ignore[arg-type]
        assert len(users) == 0

    def test_set_group_enabled(self, repository) -> None:
        group = repository.add_group(MonitoredGroup(chat_id=100, title="G", enabled=True))
        result = repository.set_group_enabled(group.id, False)  # type: ignore[arg-type]
        assert result is not None
        assert result.enabled is False


class TestWatchedUsers:
    """Tests for watched user operations — matching by user_id."""

    def test_add_user_by_id(self, repository) -> None:
        group = repository.add_group(MonitoredGroup(chat_id=100, title="G"))
        user = WatchedUser(
            group_id=group.id,  # type: ignore[arg-type]
            user_id=987654321,
            display_name="Alice",
            username="alice_old",
        )
        saved = repository.add_user(user)
        assert saved.id is not None
        assert saved.user_id == 987654321

    def test_lookup_by_telegram_user_id_not_username(self, repository) -> None:
        """User matching must use user_id, not username."""
        group = repository.add_group(MonitoredGroup(chat_id=100, title="G"))
        repository.add_user(
            WatchedUser(
                group_id=group.id,  # type: ignore[arg-type]
                user_id=42,
                display_name="Bob",
                username="bob_username",
            )
        )

        found = repository.get_user_by_telegram_id(group.id, 42)  # type: ignore[arg-type]
        assert found is not None
        assert found.user_id == 42

        not_found = repository.get_user_by_telegram_id(group.id, 999)  # type: ignore[arg-type]
        assert not_found is None

    def test_update_username_snapshot(self, repository) -> None:
        """Username can be updated as a display snapshot; user_id stays immutable."""
        group = repository.add_group(MonitoredGroup(chat_id=100, title="G"))
        user = repository.add_user(
            WatchedUser(
                group_id=group.id,  # type: ignore[arg-type]
                user_id=42,
                username="old_name",
            )
        )
        user.username = "new_name"
        updated = repository.update_user(user)
        assert updated.username == "new_name"
        assert updated.user_id == 42

    def test_upsert_admin_users(self, repository) -> None:
        group = repository.add_group(MonitoredGroup(chat_id=100, title="G"))
        admins = [
            WatchedUser(group_id=group.id, user_id=1, display_name="Admin 1", is_admin=True),  # type: ignore[arg-type]
            WatchedUser(group_id=group.id, user_id=2, display_name="Admin 2", is_admin=True),  # type: ignore[arg-type]
        ]
        count = repository.upsert_admin_users(group.id, admins)  # type: ignore[arg-type]
        assert count == 2

        # Update existing admin display name
        admins[0].display_name = "Admin One Updated"
        count = repository.upsert_admin_users(group.id, admins)  # type: ignore[arg-type]
        assert count == 2
        user = repository.get_user_by_telegram_id(group.id, 1)  # type: ignore[arg-type]
        assert user is not None
        assert user.display_name == "Admin One Updated"
        assert user.is_admin is True

    def test_unique_user_per_group(self, repository) -> None:
        group = repository.add_group(MonitoredGroup(chat_id=100, title="G"))
        repository.add_user(
            WatchedUser(group_id=group.id, user_id=42, display_name="User")  # type: ignore[arg-type]
        )
        with pytest.raises(sqlite3.IntegrityError):
            repository.add_user(
                WatchedUser(group_id=group.id, user_id=42, display_name="Duplicate")  # type: ignore[arg-type]
            )


class TestForwardedMessages:
    """Tests for duplicate forward detection."""

    def test_is_forwarded(self, repository) -> None:
        assert repository.is_forwarded(100, 1) is False

        repository.record_forward(
            ForwardedMessageRecord(
                source_chat_id=100,
                source_message_id=1,
                source_user_id=42,
                destination_chat_id=200,
                destination_message_id=10,
            )
        )
        assert repository.is_forwarded(100, 1) is True
        assert repository.is_forwarded(100, 2) is False

    def test_duplicate_forward_ignored(self, repository) -> None:
        record = ForwardedMessageRecord(
            source_chat_id=100,
            source_message_id=1,
            source_user_id=42,
            destination_chat_id=200,
            destination_message_id=10,
        )
        repository.record_forward(record)
        repository.record_forward(record)  # Should not raise
        assert repository.is_forwarded(100, 1) is True


class TestAppSettings:
    """Tests for application settings persistence."""

    def test_destination_chat(self, repository) -> None:
        settings = repository.get_app_settings()
        assert settings.destination_chat_id is None

        repository.set_destination_chat(-100999, "My Channel")
        settings = repository.get_app_settings()
        assert settings.destination_chat_id == -100999
        assert settings.destination_title == "My Channel"
