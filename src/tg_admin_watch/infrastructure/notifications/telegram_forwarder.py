"""Telegram message forwarding implementation."""

import logging
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import Message

from tg_admin_watch.core.ports import MessageForwarder
from tg_admin_watch.infrastructure.notifications.base import (
    BaseNotificationBackend,
    notification_registry,
)
from tg_admin_watch.infrastructure.telegram.formatter import MessageFormatter
from tg_admin_watch.utils.rate_limit import RateLimitHandler

logger = logging.getLogger(__name__)


class TelegramForwarder(MessageForwarder, BaseNotificationBackend):
    """Forward messages to a Telegram destination chat via Telethon.

    Preserves media (photos, videos, voice notes, documents) and captions.
    """

    def __init__(
        self,
        client: TelegramClient,
        rate_limit_handler: RateLimitHandler | None = None,
    ) -> None:
        """Initialize the forwarder.

        Args:
            client: Authenticated Telethon client.
            rate_limit_handler: Optional handler for rate limit retries.
        """
        self._client = client
        self._rate_limit = rate_limit_handler or RateLimitHandler()
        self._formatter = MessageFormatter()

    @property
    def name(self) -> str:
        return "telegram"

    async def forward_message(
        self,
        message: Any,
        *,
        destination_chat_id: int,
        header_text: str,
    ) -> int:
        """Forward a message to the destination chat preserving media.

        Strategy:
        1. For media messages: download and re-upload with header as caption
        2. For text-only: send header + original text
        3. Fallback: native Telegram forward with header sent separately
        """
        if not isinstance(message, Message):
            raise TypeError(f"Expected Telethon Message, got {type(message)}")

        if self._formatter.has_media(message):
            return await self._forward_with_media(message, destination_chat_id, header_text)
        return await self._forward_text_only(message, destination_chat_id, header_text)

    async def _forward_text_only(
        self,
        message: Message,
        destination_chat_id: int,
        header_text: str,
    ) -> int:
        """Forward a text-only message."""
        original_text = self._formatter.extract_message_text(message) or ""
        full_text = f"{header_text}\n\n{original_text}" if original_text else header_text

        result = await self._rate_limit.execute(
            lambda: self._client.send_message(
                destination_chat_id,
                full_text,
                parse_mode="md",
                link_preview=False,
            ),
            operation_name="send_text_message",
        )
        return result.id

    async def _forward_with_media(
        self,
        message: Message,
        destination_chat_id: int,
        header_text: str,
    ) -> int:
        """Forward a media message preserving the attachment and caption."""
        original_caption = self._formatter.extract_message_text(message) or ""
        caption = f"{header_text}\n\n{original_caption}" if original_caption else header_text

        try:
            result = await self._rate_limit.execute(
                lambda: self._client.send_file(
                    destination_chat_id,
                    message.media,
                    caption=caption,
                    parse_mode="md",
                ),
                operation_name="send_media_message",
            )
            return result.id
        except Exception as exc:
            logger.warning(
                "Media re-upload failed (%s), falling back to native forward",
                exc,
            )
            return await self._fallback_forward(message, destination_chat_id, header_text)

    async def _fallback_forward(
        self,
        message: Message,
        destination_chat_id: int,
        header_text: str,
    ) -> int:
        """Fallback: send header then native-forward the original message."""
        await self._rate_limit.execute(
            lambda: self._client.send_message(
                destination_chat_id,
                header_text,
                parse_mode="md",
                link_preview=False,
            ),
            operation_name="send_header",
        )

        forwarded = await self._rate_limit.execute(
            lambda: self._client.forward_messages(
                destination_chat_id,
                message,
            ),
            operation_name="forward_messages",
        )
        if isinstance(forwarded, list):
            return forwarded[0].id if forwarded else 0
        return forwarded.id

    async def send_text(self, text: str, *, destination: int | str) -> int | str:
        """Send plain text (NotificationBackend interface)."""
        result = await self._rate_limit.execute(
            lambda: self._client.send_message(destination, text),
            operation_name="notification_send_text",
        )
        return result.id

    async def send_media(
        self,
        media: Any,
        *,
        caption: str | None,
        destination: int | str,
    ) -> int | str:
        """Send media (NotificationBackend interface)."""
        result = await self._rate_limit.execute(
            lambda: self._client.send_file(destination, media, caption=caption),
            operation_name="notification_send_media",
        )
        return result.id

    async def close(self) -> None:
        """No resources to release (client managed externally)."""
        return None


# Register the default Telegram backend
notification_registry.register("telegram", TelegramForwarder)
