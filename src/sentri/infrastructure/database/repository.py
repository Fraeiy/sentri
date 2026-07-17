"""SQLite repository implementing group, user, and forward persistence."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sentri.core.models import (
    AppSettings,
    ForwardedMessageRecord,
    MonitoredGroup,
    WatchedUser,
    WatchMode,
)
from sentri.infrastructure.database.schema import CREATE_TABLES_SQL, SCHEMA_VERSION

logger = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime string from SQLite."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(UTC).isoformat()


class DatabaseRepository:
    """SQLite-backed repository for all application configuration and state."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the repository and ensure schema exists.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a database connection with row factory and foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_schema(self) -> None:
        """Create tables and set schema version if not present."""
        with self._connection() as conn:
            conn.executescript(CREATE_TABLES_SQL)
            row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
                logger.info("Initialized database schema v%d at %s", SCHEMA_VERSION, self.db_path)

    # ── App Settings ──────────────────────────────────────────────────────

    def get_app_settings(self) -> AppSettings:
        """Load application settings from the database."""
        with self._connection() as conn:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        settings_map = {row["key"]: row["value"] for row in rows}
        dest_id = settings_map.get("destination_chat_id")
        return AppSettings(
            destination_chat_id=int(dest_id) if dest_id else None,
            destination_title=settings_map.get("destination_title", ""),
        )

    def set_destination_chat(self, chat_id: int, title: str = "") -> None:
        """Persist the global default destination chat."""
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("destination_chat_id", str(chat_id)),
            )
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("destination_title", title),
            )

    # ── Monitored Groups ──────────────────────────────────────────────────

    def _row_to_group(self, row: sqlite3.Row) -> MonitoredGroup:
        """Convert a database row to a MonitoredGroup model."""
        return MonitoredGroup(
            id=row["id"],
            chat_id=row["chat_id"],
            title=row["title"],
            enabled=bool(row["enabled"]),
            watch_mode=WatchMode(row["watch_mode"]),
            destination_chat_id=row["destination_chat_id"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def get_all_groups(self, *, enabled_only: bool = False) -> list[MonitoredGroup]:
        """Return all monitored groups, optionally filtering to enabled only."""
        query = "SELECT * FROM monitored_groups"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY title COLLATE NOCASE"
        with self._connection() as conn:
            rows = conn.execute(query).fetchall()
        return [self._row_to_group(row) for row in rows]

    def get_group_by_chat_id(self, chat_id: int) -> MonitoredGroup | None:
        """Find a monitored group by its Telegram chat ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM monitored_groups WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return self._row_to_group(row) if row else None

    def get_group_by_id(self, group_id: int) -> MonitoredGroup | None:
        """Find a monitored group by its internal database ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM monitored_groups WHERE id = ?",
                (group_id,),
            ).fetchone()
        return self._row_to_group(row) if row else None

    def add_group(self, group: MonitoredGroup) -> MonitoredGroup:
        """Insert a new monitored group."""
        now = _now_iso()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monitored_groups
                    (chat_id, title, enabled, watch_mode, destination_chat_id,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group.chat_id,
                    group.title,
                    int(group.enabled),
                    group.watch_mode.value,
                    group.destination_chat_id,
                    now,
                    now,
                ),
            )
            group_id = cursor.lastrowid
        return self.get_group_by_id(group_id)  # type: ignore[return-value]

    def update_group(self, group: MonitoredGroup) -> MonitoredGroup:
        """Update an existing monitored group."""
        if group.id is None:
            raise ValueError("Cannot update group without id")
        now = _now_iso()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE monitored_groups
                SET title = ?, enabled = ?, watch_mode = ?,
                    destination_chat_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    group.title,
                    int(group.enabled),
                    group.watch_mode.value,
                    group.destination_chat_id,
                    now,
                    group.id,
                ),
            )
        return self.get_group_by_id(group.id)  # type: ignore[return-value]

    def delete_group(self, group_id: int) -> bool:
        """Delete a monitored group and its watched users (cascade)."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM monitored_groups WHERE id = ?",
                (group_id,),
            )
        return cursor.rowcount > 0

    def set_group_enabled(self, group_id: int, enabled: bool) -> MonitoredGroup | None:
        """Enable or disable a monitored group."""
        group = self.get_group_by_id(group_id)
        if group is None:
            return None
        group.enabled = enabled
        return self.update_group(group)

    # ── Watched Users ─────────────────────────────────────────────────────

    def _row_to_user(self, row: sqlite3.Row) -> WatchedUser:
        """Convert a database row to a WatchedUser model."""
        return WatchedUser(
            id=row["id"],
            group_id=row["group_id"],
            user_id=row["user_id"],
            display_name=row["display_name"],
            username=row["username"],
            is_admin=bool(row["is_admin"]),
            enabled=bool(row["enabled"]),
            created_at=_parse_datetime(row["created_at"]),
        )

    def get_users_for_group(
        self,
        group_id: int,
        *,
        enabled_only: bool = False,
    ) -> list[WatchedUser]:
        """Return watched users for a group."""
        query = "SELECT * FROM watched_users WHERE group_id = ?"
        params: list[Any] = [group_id]
        if enabled_only:
            query += " AND enabled = 1"
        query += " ORDER BY display_name COLLATE NOCASE"
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user_by_id(self, user_record_id: int) -> WatchedUser | None:
        """Find a watched user by internal database ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM watched_users WHERE id = ?",
                (user_record_id,),
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_telegram_id(self, group_id: int, user_id: int) -> WatchedUser | None:
        """Find a watched user by immutable Telegram user ID within a group."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM watched_users WHERE group_id = ? AND user_id = ?",
                (group_id, user_id),
            ).fetchone()
        return self._row_to_user(row) if row else None

    def add_user(self, user: WatchedUser) -> WatchedUser:
        """Insert a new watched user (matched by user_id, not username)."""
        now = _now_iso()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO watched_users
                    (group_id, user_id, display_name, username, is_admin, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.group_id,
                    user.user_id,
                    user.display_name,
                    user.username,
                    int(user.is_admin),
                    int(user.enabled),
                    now,
                ),
            )
            user_id = cursor.lastrowid
        return self.get_user_by_id(user_id)  # type: ignore[return-value]

    def update_user(self, user: WatchedUser) -> WatchedUser:
        """Update display info for a watched user (user_id is immutable)."""
        if user.id is None:
            raise ValueError("Cannot update user without id")
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE watched_users
                SET display_name = ?, username = ?, is_admin = ?, enabled = ?
                WHERE id = ?
                """,
                (
                    user.display_name,
                    user.username,
                    int(user.is_admin),
                    int(user.enabled),
                    user.id,
                ),
            )
        return self.get_user_by_id(user.id)  # type: ignore[return-value]

    def delete_user(self, user_record_id: int) -> bool:
        """Remove a watched user."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM watched_users WHERE id = ?",
                (user_record_id,),
            )
        return cursor.rowcount > 0

    def delete_users_for_group(self, group_id: int) -> int:
        """Remove all watched users for a group."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM watched_users WHERE group_id = ?",
                (group_id,),
            )
        return cursor.rowcount

    def upsert_admin_users(self, group_id: int, admins: list[WatchedUser]) -> int:
        """Insert or update admin users discovered from Telegram.

        Matching is always by ``user_id``.

        Returns:
            Number of users upserted.
        """
        count = 0
        for admin in admins:
            existing = self.get_user_by_telegram_id(group_id, admin.user_id)
            if existing:
                existing.display_name = admin.display_name
                existing.username = admin.username
                existing.is_admin = True
                self.update_user(existing)
            else:
                admin.group_id = group_id
                admin.is_admin = True
                self.add_user(admin)
            count += 1
        return count

    # ── Forwarded Messages (deduplication) ────────────────────────────────

    def is_forwarded(self, source_chat_id: int, source_message_id: int) -> bool:
        """Check whether a message has already been forwarded."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM forwarded_messages
                WHERE source_chat_id = ? AND source_message_id = ?
                """,
                (source_chat_id, source_message_id),
            ).fetchone()
        return row is not None

    def record_forward(self, record: ForwardedMessageRecord) -> ForwardedMessageRecord:
        """Record a forwarded message to prevent future duplicates."""
        now = _now_iso()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO forwarded_messages
                    (source_chat_id, source_message_id, source_user_id,
                     destination_chat_id, destination_message_id, forwarded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_chat_id,
                    record.source_message_id,
                    record.source_user_id,
                    record.destination_chat_id,
                    record.destination_message_id,
                    now,
                ),
            )
            record_id = cursor.lastrowid
        if record_id:
            record.id = record_id
            record.forwarded_at = _parse_datetime(now)
        return record
