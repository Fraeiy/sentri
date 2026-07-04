"""Pytest fixtures and configuration."""

import os
from pathlib import Path

import pytest

# Set test environment variables before any settings are loaded
os.environ.setdefault("TELEGRAM_API_ID", "12345678")
os.environ.setdefault("TELEGRAM_API_HASH", "test_api_hash_for_unit_tests")


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def repository(tmp_db_path: Path):
    """Return a DatabaseRepository backed by a temporary database."""
    from tg_admin_watch.infrastructure.database.repository import DatabaseRepository

    return DatabaseRepository(tmp_db_path)
