"""Domain models for Sentri.

All user identity matching uses immutable Telegram user IDs. Display names and
usernames are stored for CLI convenience but are never used for matching logic.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WatchMode(StrEnum):
    """How watched users are determined for a monitored group."""

    ADMINS_ONLY = "admins_only"
    SELECTED_USERS = "selected_users"
    ADMINS_AND_SELECTED = "admins_and_selected"


class MonitoredGroup(BaseModel):
    """A Telegram group or channel being monitored."""

    id: int | None = None
    chat_id: int = Field(..., description="Immutable Telegram chat ID")
    title: str = Field(default="", description="Display title for CLI")
    enabled: bool = Field(default=True)
    watch_mode: WatchMode = Field(default=WatchMode.SELECTED_USERS)
    destination_chat_id: int | None = Field(
        default=None,
        description="Destination chat for forwards; None uses global default",
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WatchedUser(BaseModel):
    """A user whose messages should be forwarded from a monitored group.

    Matching is always performed by ``user_id``, never by username.
    """

    id: int | None = None
    group_id: int = Field(..., description="FK to monitored_groups.id")
    user_id: int = Field(..., description="Immutable Telegram user ID")
    display_name: str = Field(
        default="",
        description="First + last name snapshot for CLI display",
    )
    username: str | None = Field(
        default=None,
        description="Username snapshot for CLI display; may change on Telegram",
    )
    is_admin: bool = Field(
        default=False,
        description="Whether user was added as an admin (auto-discovered)",
    )
    enabled: bool = Field(default=True)
    created_at: datetime | None = None


class ForwardedMessageRecord(BaseModel):
    """Record of a forwarded message to prevent duplicates."""

    id: int | None = None
    source_chat_id: int
    source_message_id: int
    source_user_id: int
    destination_chat_id: int
    destination_message_id: int | None = None
    forwarded_at: datetime | None = None


class AppSettings(BaseModel):
    """Application-level settings stored in SQLite."""

    destination_chat_id: int | None = Field(
        default=None,
        description="Global default destination chat for forwards",
    )
    destination_title: str = Field(default="")


class TelegramUserInfo(BaseModel):
    """Lightweight user info for display purposes."""

    user_id: int
    display_name: str = ""
    username: str | None = None
    is_admin: bool = False
