"""Pydantic-based application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for TG Admin Watch.

    Values are loaded from environment variables and an optional ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TG_ADMIN_WATCH_",
        extra="ignore",
    )

    # Telegram API credentials (also read without prefix for convenience)
    telegram_api_id: int = Field(
        ...,
        validation_alias="TELEGRAM_API_ID",
        description="Telegram API ID from https://my.telegram.org/apps",
    )
    telegram_api_hash: str = Field(
        ...,
        validation_alias="TELEGRAM_API_HASH",
        description="Telegram API hash from https://my.telegram.org/apps",
    )

    data_dir: Path = Field(default=Path("./data"))
    db_path: Path | None = Field(default=None)
    session_path: Path | None = Field(default=None)
    log_level: str = Field(default="INFO")
    log_file: Path | None = Field(default=None)

    reconnect_max_delay: float = Field(default=300.0, ge=1.0)
    reconnect_base_delay: float = Field(default=1.0, ge=0.1)
    rate_limit_max_retries: int = Field(default=5, ge=1)
    rate_limit_base_delay: float = Field(default=2.0, ge=0.5)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize log level to uppercase."""
        return value.upper()

    @property
    def resolved_db_path(self) -> Path:
        """Return the SQLite database file path."""
        if self.db_path is not None:
            return self.db_path
        return self.data_dir / "tg_admin_watch.db"

    @property
    def resolved_session_path(self) -> Path:
        """Return the Telethon session file path (without extension)."""
        if self.session_path is not None:
            return self.session_path
        return self.data_dir / "session"

    @property
    def resolved_log_file(self) -> Path | None:
        """Return the log file path, defaulting under data_dir when unset."""
        if self.log_file is not None:
            return self.log_file
        return self.data_dir / "tg_admin_watch.log"

    def ensure_directories(self) -> None:
        """Create required data directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.resolved_log_file
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    settings = Settings()  # type: ignore[call-arg]
    settings.ensure_directories()
    return settings
