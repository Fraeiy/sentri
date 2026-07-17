"""Pydantic schemas for web API requests and responses."""

from pydantic import BaseModel, Field

from sentri.core.models import WatchMode


class GroupCreate(BaseModel):
    """Request body for creating a monitored group."""

    chat_id: int
    title: str = ""
    watch_mode: WatchMode = WatchMode.SELECTED_USERS


class GroupUpdate(BaseModel):
    """Request body for updating a monitored group."""

    title: str | None = None
    watch_mode: WatchMode | None = None
    destination_chat_id: int | None = None
    enabled: bool | None = None


class UserCreate(BaseModel):
    """Request body for adding a watched user."""

    user_id: int = Field(..., description="Immutable Telegram user ID")
    display_name: str = ""
    username: str | None = None


class DestinationSet(BaseModel):
    """Request body for setting the global destination."""

    chat_id: int
    title: str = ""


class AuthPhoneRequest(BaseModel):
    """Phone number for Telegram authentication."""

    phone: str


class AuthCodeRequest(BaseModel):
    """Verification code for Telegram authentication."""

    code: str


class AuthPasswordRequest(BaseModel):
    """2FA password for Telegram authentication."""

    password: str
