"""Notification backend adapters."""

from sentri.infrastructure.notifications.base import BaseNotificationBackend
from sentri.infrastructure.notifications.telegram_forwarder import TelegramForwarder

__all__ = ["BaseNotificationBackend", "TelegramForwarder"]
