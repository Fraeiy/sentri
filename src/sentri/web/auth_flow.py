"""In-memory Telegram authentication flow for the web UI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from telethon.errors import SessionPasswordNeededError

if TYPE_CHECKING:
    from telethon import TelegramClient

from sentri.config.settings import Settings
from sentri.infrastructure.telegram.client import TelegramClientManager

logger = logging.getLogger(__name__)


@dataclass
class AuthFlowState:
    """Tracks multi-step Telegram login progress."""

    step: str = "idle"  # idle | code_sent | needs_password | done | error
    phone: str = ""
    message: str = ""
    error: str = ""


class WebAuthFlow:
    """Handles Telegram phone/code/2FA authentication via the web UI."""

    _instance: "WebAuthFlow | None" = None

    def __init__(self) -> None:
        self.state = AuthFlowState()
        self._client: TelegramClient | None = None
        self._manager: TelegramClientManager | None = None

    @classmethod
    def get_instance(cls) -> "WebAuthFlow":
        """Return the global auth flow singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def send_code(self, settings: Settings, phone: str) -> AuthFlowState:
        """Send a verification code to the given phone number."""
        await self._reset()
        self._manager = TelegramClientManager(settings)
        self._client = self._manager.create_client()
        await self._client.connect()

        if await self._client.is_user_authorized():
            self.state = AuthFlowState(
                step="done",
                phone=phone,
                message="Already authenticated.",
            )
            await self._cleanup()
            return self.state

        await self._client.send_code_request(phone)
        self.state = AuthFlowState(
            step="code_sent",
            phone=phone,
            message="Verification code sent. Check your Telegram app.",
        )
        return self.state

    async def submit_code(self, code: str) -> AuthFlowState:
        """Submit the verification code."""
        if self._client is None or not self.state.phone:
            self.state = AuthFlowState(step="error", error="Start by submitting your phone number.")
            return self.state

        try:
            await self._client.sign_in(self.state.phone, code)
            self.state = AuthFlowState(
                step="done",
                phone=self.state.phone,
                message="Authenticated!",
            )
            await self._cleanup()
        except SessionPasswordNeededError:
            self.state = AuthFlowState(
                step="needs_password",
                phone=self.state.phone,
                message="Two-factor authentication required.",
            )
        except Exception as exc:
            self.state = AuthFlowState(step="error", error=str(exc))
            await self._cleanup()
        return self.state

    async def submit_password(self, password: str) -> AuthFlowState:
        """Submit 2FA password."""
        if self._client is None:
            self.state = AuthFlowState(step="error", error="Authentication session expired.")
            return self.state

        try:
            await self._client.sign_in(password=password)
            self.state = AuthFlowState(
                step="done",
                phone=self.state.phone,
                message="Authenticated with 2FA!",
            )
        except Exception as exc:
            self.state = AuthFlowState(step="error", error=str(exc))
        finally:
            await self._cleanup()
        return self.state

    async def _reset(self) -> None:
        await self._cleanup()
        self.state = AuthFlowState()

    async def _cleanup(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception as exc:
                logger.debug("Auth cleanup error: %s", exc)
        self._client = None
        self._manager = None
