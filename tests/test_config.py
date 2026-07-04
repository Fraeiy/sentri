"""Tests for application configuration."""

from pathlib import Path

import pytest


class TestSettings:
    """Tests for Pydantic settings."""

    def test_settings_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "99999")
        monkeypatch.setenv("TELEGRAM_API_HASH", "abc123hash")
        monkeypatch.setenv("TG_ADMIN_WATCH_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("TG_ADMIN_WATCH_LOG_LEVEL", "debug")

        # Clear cached settings
        from tg_admin_watch.config.settings import Settings, get_settings

        get_settings.cache_clear()

        settings = Settings()  # type: ignore[call-arg]
        assert settings.telegram_api_id == 99999
        assert settings.telegram_api_hash == "abc123hash"
        assert settings.data_dir == tmp_path / "data"
        assert settings.log_level == "DEBUG"

        get_settings.cache_clear()

    def test_resolved_paths(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "1")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TG_ADMIN_WATCH_DATA_DIR", str(tmp_path))

        from tg_admin_watch.config.settings import Settings

        settings = Settings()  # type: ignore[call-arg]
        assert settings.resolved_db_path == tmp_path / "tg_admin_watch.db"
        assert settings.resolved_session_path == tmp_path / "session"

    def test_ensure_directories(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "1")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TG_ADMIN_WATCH_DATA_DIR", str(tmp_path / "nested" / "data"))

        from tg_admin_watch.config.settings import Settings

        settings = Settings()  # type: ignore[call-arg]
        settings.ensure_directories()
        assert settings.data_dir.exists()
