"""Rate limit handling with exponential backoff."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from telethon.errors import FloodWaitError, RPCError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RateLimitHandler:
    """Execute async operations with retry logic for Telegram rate limits."""

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 2.0,
    ) -> None:
        """Initialize the handler.

        Args:
            max_retries: Maximum number of retry attempts after rate limiting.
            base_delay: Base delay in seconds for exponential backoff.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        operation_name: str = "operation",
    ) -> T:
        """Execute an async operation with flood-wait and RPC error handling.

        Args:
            operation: Async callable to execute.
            operation_name: Human-readable name for log messages.

        Returns:
            The result of the operation.

        Raises:
            FloodWaitError: If rate limit persists beyond max retries.
            RPCError: If a non-recoverable RPC error occurs.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation()
            except FloodWaitError as exc:
                wait_seconds = exc.seconds + 1
                logger.warning(
                    "Flood wait on %s: sleeping %d seconds (attempt %d/%d)",
                    operation_name,
                    wait_seconds,
                    attempt + 1,
                    self.max_retries + 1,
                )
                await asyncio.sleep(wait_seconds)
                last_error = exc
            except RPCError as exc:
                if attempt < self.max_retries and self._is_retryable(exc):
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        "RPC error on %s: %s — retrying in %.1fs (attempt %d/%d)",
                        operation_name,
                        exc,
                        delay,
                        attempt + 1,
                        self.max_retries + 1,
                    )
                    await asyncio.sleep(delay)
                    last_error = exc
                else:
                    raise

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Rate limit handler failed for {operation_name}")

    @staticmethod
    def _is_retryable(error: RPCError) -> bool:
        """Determine whether an RPC error is worth retrying."""
        message = str(error).lower()
        retryable_patterns = (
            "timeout",
            "connection",
            "server",
            "internal",
            "temporarily",
        )
        return any(pattern in message for pattern in retryable_patterns)
