"""Notification backend adapters."""

from tg_admin_watch.infrastructure.notifications.base import BaseNotificationBackend
from tg_admin_watch.infrastructure.notifications.telegram_forwarder import TelegramForwarder

__all__ = ["BaseNotificationBackend", "TelegramForwarder"]
