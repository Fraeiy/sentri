"""Telegram event listener for new messages in monitored groups."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from telethon import TelegramClient, events
from telethon.tl.types import User

from sentri.core.models import MonitoredGroup, WatchMode
from sentri.infrastructure.database.repository import DatabaseRepository
from sentri.infrastructure.telegram.formatter import MessageFormatter

logger = logging.getLogger(__name__)

MessageHandler = Callable[[Any, MonitoredGroup, int], Awaitable[None]]


class EventListener:
    """Register Telethon event handlers for monitored groups.

    User matching is performed exclusively by Telegram user ID, never username.
    """

    def __init__(
        self,
        client: TelegramClient,
        repository: DatabaseRepository,
        on_message: MessageHandler,
    ) -> None:
        """Initialize the event listener.

        Args:
            client: Authenticated Telethon client.
            repository: Database repository for configuration lookups.
            on_message: Async callback invoked for messages that should be forwarded.
                Receives (message, group, sender_user_id).
        """
        self._client = client
        self._repository = repository
        self._on_message = on_message
        self._formatter = MessageFormatter()
        self._admin_cache: dict[int, set[int]] = {}
        self._handler: Callable[..., Any] | None = None

    def register(self) -> None:
        """Register the new-message event handler on the client."""
        monitored_chat_ids = self._get_monitored_chat_ids()
        if not monitored_chat_ids:
            logger.warning("No enabled monitored groups — event listener inactive")
            return

        @self._client.on(events.NewMessage(chats=monitored_chat_ids))
        async def handler(event: events.NewMessage.Event) -> None:
            await self._handle_new_message(event)

        self._handler = handler
        logger.info(
            "Event listener registered for %d chat(s): %s",
            len(monitored_chat_ids),
            monitored_chat_ids,
        )

    def refresh(self) -> None:
        """Re-register handlers after configuration changes."""
        if self._handler is not None:
            self._client.remove_event_handler(self._handler)
        self._admin_cache.clear()
        self.register()

    def _get_monitored_chat_ids(self) -> list[int]:
        """Return chat IDs of all enabled monitored groups."""
        groups = self._repository.get_all_groups(enabled_only=True)
        return [g.chat_id for g in groups]

    async def _handle_new_message(self, event: events.NewMessage.Event) -> None:
        """Process an incoming message and dispatch if from a watched user."""
        message = event.message
        chat_id = event.chat_id

        if chat_id is None:
            return

        group = self._repository.get_group_by_chat_id(chat_id)
        if group is None or not group.enabled:
            return

        sender_id = await self._resolve_sender_id(message)
        if sender_id is None:
            logger.debug("Could not resolve sender for message %d in chat %d", message.id, chat_id)
            return

        if not await self._should_forward(group, sender_id):
            return

        if self._repository.is_forwarded(chat_id, message.id):
            logger.debug(
                "Skipping duplicate: chat=%d msg=%d",
                chat_id,
                message.id,
            )
            return

        logger.info(
            "Matched message from user_id=%d in group '%s' (chat_id=%d)",
            sender_id,
            group.title,
            chat_id,
        )
        await self._on_message(message, group, sender_id)

    async def _resolve_sender_id(self, message: Any) -> int | None:
        """Resolve the sender's immutable Telegram user ID."""
        sender_id = getattr(message, "sender_id", None)
        if sender_id is not None and sender_id > 0:
            return sender_id

        sender = await message.get_sender()
        if isinstance(sender, User):
            return sender.id

        from_id = getattr(message, "from_id", None)
        if from_id is not None:
            user_id = getattr(from_id, "user_id", None)
            if user_id:
                return user_id

        return None

    async def _should_forward(self, group: MonitoredGroup, sender_id: int) -> bool:
        """Determine whether a message from sender_id should be forwarded.

        Matching is always by user_id, never username.
        """
        mode = group.watch_mode

        if mode in (WatchMode.SELECTED_USERS, WatchMode.ADMINS_AND_SELECTED):
            watched = self._repository.get_user_by_telegram_id(group.id, sender_id)  # type: ignore[arg-type]
            if watched and watched.enabled:
                return True

        if mode in (WatchMode.ADMINS_ONLY, WatchMode.ADMINS_AND_SELECTED):
            admin_ids = await self._get_admin_ids(group)
            if sender_id in admin_ids:
                return True

        return False

    async def _get_admin_ids(self, group: MonitoredGroup) -> set[int]:
        """Return cached admin user IDs for a group."""
        if group.id is None:
            return set()

        if group.id in self._admin_cache:
            return self._admin_cache[group.id]

        try:
            from telethon.tl.types import ChannelParticipantsAdmins

            participants = await self._client.get_participants(
                group.chat_id,
                filter=ChannelParticipantsAdmins(),
            )
            admin_ids = {p.id for p in participants if isinstance(p, User)}
            self._admin_cache[group.id] = admin_ids
            return admin_ids
        except Exception as exc:
            logger.warning("Failed to fetch admins for group %d: %s", group.chat_id, exc)
            return set()
