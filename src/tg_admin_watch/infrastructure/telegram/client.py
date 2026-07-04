"""Telethon client management with auto-reconnect."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import (
    AuthKeyUnregisteredError,
    SessionPasswordNeededError,
    UserDeactivatedError,
)

from tg_admin_watch.config.settings import Settings

logger = logging.getLogger(__name__)


class TelegramClientManager:
    """Manages the Telethon client lifecycle including authentication and reconnection."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the client manager.

        Args:
            settings: Application settings containing API credentials and paths.
        """
        self.settings = settings
        self._client: TelegramClient | None = None
        self._reconnecting = False

    @property
    def client(self) -> TelegramClient:
        """Return the active Telethon client, raising if not connected."""
        if self._client is None:
            raise RuntimeError("Telegram client is not initialized. Call connect() first.")
        return self._client

    def create_client(self) -> TelegramClient:
        """Create a new Telethon client instance."""
        session_path = str(self.settings.resolved_session_path)
        self._client = TelegramClient(
            session_path,
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        )
        return self._client

    async def connect(self) -> TelegramClient:
        """Connect to Telegram and authenticate if needed."""
        if self._client is None:
            self.create_client()

        assert self._client is not None
        await self._client.connect()

        if not await self._client.is_user_authorized():
            raise RuntimeError("Not authorized. Run 'tg-admin-watch auth' to authenticate first.")

        me = await self._client.get_me()
        logger.info(
            "Connected as %s (user_id=%d)",
            me.first_name if me else "unknown",
            me.id if me else 0,
        )
        return self._client

    async def authenticate_interactive(
        self,
        phone_callback: Callable[[], str],
        code_callback: Callable[[], str],
        password_callback: Callable[[], str] | None = None,
    ) -> None:
        """Perform interactive authentication with the user's personal account.

        Args:
            phone_callback: Callable returning the phone number.
            code_callback: Callable returning the verification code.
            password_callback: Optional callable for 2FA password.
        """
        if self._client is None:
            self.create_client()

        assert self._client is not None
        await self._client.connect()

        if await self._client.is_user_authorized():
            me = await self._client.get_me()
            logger.info("Already authorized as user_id=%d", me.id if me else 0)
            return

        phone = phone_callback()
        await self._client.send_code_request(phone)
        code = code_callback()

        try:
            await self._client.sign_in(phone, code)
        except SessionPasswordNeededError as exc:
            if password_callback is None:
                raise RuntimeError(
                    "Two-factor authentication is enabled. Password required."
                ) from exc
            password = password_callback()
            await self._client.sign_in(password=password)

        me = await self._client.get_me()
        logger.info("Authenticated successfully as user_id=%d", me.id if me else 0)

    async def disconnect(self) -> None:
        """Disconnect the Telethon client."""
        if self._client is not None:
            await self._client.disconnect()
            logger.info("Disconnected from Telegram")

    async def run_with_reconnect(
        self,
        run_callback: Callable[[TelegramClient], Awaitable[None]],
    ) -> None:
        """Run a callback with automatic reconnection on network failures.

        Args:
            run_callback: Async function that receives the client and runs
                until cancelled or a fatal error occurs.
        """
        delay = self.settings.reconnect_base_delay
        max_delay = self.settings.reconnect_max_delay

        while True:
            try:
                await self.connect()
                await run_callback(self.client)
                break
            except (TimeoutError, ConnectionError, OSError) as exc:
                logger.warning("Connection lost: %s — reconnecting in %.1fs", exc, delay)
                await self._safe_disconnect()
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
            except (AuthKeyUnregisteredError, UserDeactivatedError) as exc:
                logger.error("Fatal auth error: %s — cannot reconnect", exc)
                raise
            except asyncio.CancelledError:
                logger.info("Watch cancelled, shutting down")
                await self._safe_disconnect()
                raise
            except Exception:
                logger.exception("Unexpected error in watch loop")
                await self._safe_disconnect()
                raise

    async def _safe_disconnect(self) -> None:
        """Disconnect without raising on errors."""
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception as exc:
                logger.debug("Error during disconnect: %s", exc)

    async def get_dialogs(self) -> list[Any]:
        """Return all user dialogs (chats, groups, channels)."""
        dialogs = []
        async for dialog in self.client.iter_dialogs():
            dialogs.append(dialog)
        return dialogs

    async def get_chat_admins(self, chat_id: int) -> list[Any]:
        """Return admin participants for a chat."""
        from telethon.tl.types import ChannelParticipantsAdmins

        participants = await self.client.get_participants(
            chat_id,
            filter=ChannelParticipantsAdmins(),
        )
        return list(participants)

    async def resolve_entity(self, entity_id: int) -> Any:
        """Resolve a chat or user entity by ID."""
        return await self.client.get_entity(entity_id)

    @staticmethod
    def session_exists(session_path: Path) -> bool:
        """Check whether a Telethon session file exists."""
        return session_path.with_suffix(".session").exists()
