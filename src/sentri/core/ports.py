"""Abstract ports (interfaces) for infrastructure adapters.

These protocols define the contracts that notification backends and forwarders
must implement, enabling future extensions (Discord, Slack, Email, ntfy, etc.)
without changing core business logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from sentri.core.models import ForwardedMessageRecord, MonitoredGroup, WatchedUser


@runtime_checkable
class NotificationBackend(Protocol):
    """Protocol for delivering notifications to external services."""

    @property
    def name(self) -> str:
        """Human-readable backend name."""
        ...

    async def send_text(self, text: str, *, destination: int | str) -> int | str:
        """Send a plain-text notification.

        Returns:
            An identifier for the sent message (backend-specific).
        """
        ...

    async def send_media(
        self,
        media: Any,
        *,
        caption: str | None,
        destination: int | str,
    ) -> int | str:
        """Send a media notification with optional caption.

        Returns:
            An identifier for the sent message (backend-specific).
        """
        ...

    async def close(self) -> None:
        """Release any resources held by the backend."""
        ...


class MessageForwarder(ABC):
    """Abstract base for message forwarding implementations."""

    @abstractmethod
    async def forward_message(
        self,
        message: Any,
        *,
        destination_chat_id: int,
        header_text: str,
    ) -> int:
        """Forward a Telegram message to a destination chat.

        Args:
            message: The source Telethon Message object.
            destination_chat_id: Target chat ID.
            header_text: Formatted header to prepend or send alongside.

        Returns:
            The ID of the forwarded/sent message in the destination chat.
        """
        ...


class GroupRepository(Protocol):
    """Repository contract for monitored group persistence."""

    def get_all_groups(self) -> list[MonitoredGroup]: ...
    def get_group_by_chat_id(self, chat_id: int) -> MonitoredGroup | None: ...
    def get_group_by_id(self, group_id: int) -> MonitoredGroup | None: ...
    def add_group(self, group: MonitoredGroup) -> MonitoredGroup: ...
    def update_group(self, group: MonitoredGroup) -> MonitoredGroup: ...
    def delete_group(self, group_id: int) -> bool: ...


class UserRepository(Protocol):
    """Repository contract for watched user persistence."""

    def get_users_for_group(self, group_id: int) -> list[WatchedUser]: ...
    def get_user_by_id(self, user_record_id: int) -> WatchedUser | None: ...
    def get_user_by_telegram_id(self, group_id: int, user_id: int) -> WatchedUser | None: ...
    def add_user(self, user: WatchedUser) -> WatchedUser: ...
    def update_user(self, user: WatchedUser) -> WatchedUser: ...
    def delete_user(self, user_record_id: int) -> bool: ...
    def delete_users_for_group(self, group_id: int) -> int: ...


class ForwardRepository(Protocol):
    """Repository contract for forwarded message deduplication."""

    def is_forwarded(self, source_chat_id: int, source_message_id: int) -> bool: ...
    def record_forward(self, record: ForwardedMessageRecord) -> ForwardedMessageRecord: ...
