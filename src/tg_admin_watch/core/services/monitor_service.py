"""Monitor service — orchestrates watching and forwarding."""

import logging
from typing import Any

from tg_admin_watch.config.settings import Settings
from tg_admin_watch.core.models import ForwardedMessageRecord
from tg_admin_watch.infrastructure.database.repository import DatabaseRepository
from tg_admin_watch.infrastructure.notifications.telegram_forwarder import TelegramForwarder
from tg_admin_watch.infrastructure.telegram.client import TelegramClientManager
from tg_admin_watch.infrastructure.telegram.events import EventListener
from tg_admin_watch.infrastructure.telegram.formatter import MessageFormatter
from tg_admin_watch.utils.rate_limit import RateLimitHandler

logger = logging.getLogger(__name__)


class MonitorService:
    """Core service that wires together listening, filtering, and forwarding.

    Business logic lives here; infrastructure details are injected via
    constructor dependencies (clean architecture).
    """

    def __init__(
        self,
        settings: Settings,
        repository: DatabaseRepository,
        client_manager: TelegramClientManager,
    ) -> None:
        """Initialize the monitor service.

        Args:
            settings: Application settings.
            repository: SQLite repository for configuration and deduplication.
            client_manager: Telethon client lifecycle manager.
        """
        self._settings = settings
        self._repository = repository
        self._client_manager = client_manager
        self._formatter = MessageFormatter()
        self._rate_limit = RateLimitHandler(
            max_retries=settings.rate_limit_max_retries,
            base_delay=settings.rate_limit_base_delay,
        )
        self._event_listener: EventListener | None = None
        self._forwarder: TelegramForwarder | None = None

    async def start(self) -> None:
        """Start monitoring with auto-reconnect."""
        await self._client_manager.run_with_reconnect(self._run_watch)

    async def _run_watch(self, client: Any) -> None:
        """Set up event listener and run until disconnected."""
        self._forwarder = TelegramForwarder(client, self._rate_limit)
        self._event_listener = EventListener(
            client=client,
            repository=self._repository,
            on_message=self._handle_message,
        )
        self._event_listener.register()

        groups = self._repository.get_all_groups(enabled_only=True)
        if not groups:
            logger.warning("No enabled groups configured. Add groups via the CLI.")
        else:
            logger.info("Watching %d enabled group(s)", len(groups))

        app_settings = self._repository.get_app_settings()
        if app_settings.destination_chat_id:
            logger.info(
                "Default destination: %s (chat_id=%d)",
                app_settings.destination_title or "unnamed",
                app_settings.destination_chat_id,
            )
        else:
            logger.warning(
                "No global destination set. Configure per-group destinations or "
                "run 'tg-admin-watch config set-destination'."
            )

        logger.info("Monitor active — press Ctrl+C to stop")
        await client.run_until_disconnected()

    async def _handle_message(
        self,
        message: Any,
        group: Any,
        sender_user_id: int,
    ) -> None:
        """Handle a matched message: format, forward, and record."""
        if self._forwarder is None:
            logger.error("Forwarder not initialized")
            return

        destination_chat_id = self._resolve_destination(group)
        if destination_chat_id is None:
            logger.error(
                "No destination configured for group '%s' (chat_id=%d)",
                group.title,
                group.chat_id,
            )
            return

        sender = await self._resolve_sender_info(message, sender_user_id)
        header = self._formatter.build_forward_header(
            group=group,
            sender=sender,
            message_date=message.date,
            original_text_preview=self._formatter.extract_message_text(message),
        )

        try:
            dest_message_id = await self._forwarder.forward_message(
                message,
                destination_chat_id=destination_chat_id,
                header_text=header,
            )

            self._repository.record_forward(
                ForwardedMessageRecord(
                    source_chat_id=group.chat_id,
                    source_message_id=message.id,
                    source_user_id=sender_user_id,
                    destination_chat_id=destination_chat_id,
                    destination_message_id=dest_message_id,
                )
            )

            logger.info(
                "Forwarded msg %d from user_id=%d → destination %d (msg %d)",
                message.id,
                sender_user_id,
                destination_chat_id,
                dest_message_id,
            )
        except Exception:
            logger.exception(
                "Failed to forward message %d from user_id=%d",
                message.id,
                sender_user_id,
            )

    def _resolve_destination(self, group: Any) -> int | None:
        """Resolve the destination chat ID for a group."""
        if group.destination_chat_id is not None:
            return group.destination_chat_id
        app_settings = self._repository.get_app_settings()
        return app_settings.destination_chat_id

    async def _resolve_sender_info(self, message: Any, sender_user_id: int) -> Any:
        """Resolve sender display info, falling back to user_id only."""
        from tg_admin_watch.core.models import TelegramUserInfo

        try:
            sender = await message.get_sender()
            if sender is not None:
                return self._formatter.user_info_from_telethon(sender)
        except Exception as exc:
            logger.debug("Could not fetch sender entity: %s", exc)

        return TelegramUserInfo(
            user_id=sender_user_id,
            display_name=f"User (id:{sender_user_id})",
        )
