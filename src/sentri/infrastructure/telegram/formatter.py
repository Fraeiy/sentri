"""Message formatting for forwarded notifications."""

from datetime import datetime
from typing import Any

from sentri.core.models import MonitoredGroup, TelegramUserInfo


class MessageFormatter:
    """Format message headers and metadata for forwarding."""

    @staticmethod
    def build_user_display_name(
        first_name: str | None,
        last_name: str | None = None,
        username: str | None = None,
        user_id: int | None = None,
    ) -> str:
        """Build a human-readable display name from user attributes.

        The display name is for CLI/logging only; matching uses user_id.
        """
        parts = []
        if first_name:
            parts.append(first_name)
        if last_name:
            parts.append(last_name)
        name = " ".join(parts) if parts else "Unknown"

        extras = []
        if username:
            extras.append(f"@{username}")
        if user_id is not None:
            extras.append(f"id:{user_id}")

        if extras:
            return f"{name} ({', '.join(extras)})"
        return name

    @staticmethod
    def user_info_from_telethon(user: Any) -> TelegramUserInfo:
        """Extract TelegramUserInfo from a Telethon User object."""
        first = getattr(user, "first_name", None) or ""
        last = getattr(user, "last_name", None) or ""
        username = getattr(user, "username", None)
        user_id = getattr(user, "id", 0)

        return TelegramUserInfo(
            user_id=user_id,
            display_name=MessageFormatter.build_user_display_name(first, last, username, user_id),
            username=username,
        )

    @staticmethod
    def build_forward_header(
        *,
        group: MonitoredGroup,
        sender: TelegramUserInfo,
        message_date: datetime | None = None,
        original_text_preview: str | None = None,
    ) -> str:
        """Build a header string prepended to forwarded messages."""
        lines = [
            f"📨 **{group.title or 'Unknown Group'}**",
            f"👤 {sender.display_name}",
        ]

        if message_date:
            lines.append(f"🕐 {message_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        if original_text_preview:
            preview = original_text_preview[:200]
            if len(original_text_preview) > 200:
                preview += "…"
            lines.append(f"💬 {preview}")

        lines.append("—" * 20)
        return "\n".join(lines)

    @staticmethod
    def extract_message_text(message: Any) -> str | None:
        """Extract plain text or caption from a Telethon message."""
        text = getattr(message, "message", None) or getattr(message, "text", None)
        if text:
            return str(text)
        return None

    @staticmethod
    def has_media(message: Any) -> bool:
        """Check whether a message contains media."""
        return getattr(message, "media", None) is not None

    @staticmethod
    def get_media_type(message: Any) -> str | None:
        """Return a human-readable media type for a message."""
        media = getattr(message, "media", None)
        if media is None:
            return None

        type_name = type(media).__name__
        mapping = {
            "MessageMediaPhoto": "photo",
            "MessageMediaDocument": "document",
            "MessageMediaWebPage": "webpage",
            "MessageMediaGeo": "location",
            "MessageMediaContact": "contact",
            "MessageMediaPoll": "poll",
            "MessageMediaDice": "dice",
            "MessageMediaGame": "game",
            "MessageMediaInvoice": "invoice",
        }
        media_type = mapping.get(type_name, "media")

        document = getattr(media, "document", None)
        if document:
            mime = ""
            for attr in getattr(document, "attributes", []):
                attr_type = type(attr).__name__
                if attr_type == "DocumentAttributeAudio":
                    if getattr(attr, "voice", False):
                        return "voice"
                    return "audio"
                if attr_type == "DocumentAttributeVideo":
                    if getattr(attr, "round_message", False):
                        return "video_note"
                    return "video"
                if attr_type == "DocumentAttributeSticker":
                    return "sticker"
                if attr_type == "DocumentAttributeAnimated":
                    return "gif"
            if hasattr(document, "mime_type"):
                mime = document.mime_type or ""
            if "image" in mime:
                return "image"
            if "video" in mime:
                return "video"

        return media_type
