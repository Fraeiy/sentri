"""SQLite schema definitions and migrations."""

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitored_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    watch_mode TEXT NOT NULL DEFAULT 'selected_users',
    destination_chat_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watched_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    username TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (group_id) REFERENCES monitored_groups(id) ON DELETE CASCADE,
    UNIQUE (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS forwarded_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_chat_id INTEGER NOT NULL,
    source_message_id INTEGER NOT NULL,
    source_user_id INTEGER NOT NULL,
    destination_chat_id INTEGER NOT NULL,
    destination_message_id INTEGER,
    forwarded_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source_chat_id, source_message_id)
);

CREATE INDEX IF NOT EXISTS idx_watched_users_group_id
    ON watched_users(group_id);

CREATE INDEX IF NOT EXISTS idx_watched_users_user_id
    ON watched_users(user_id);

CREATE INDEX IF NOT EXISTS idx_forwarded_messages_source
    ON forwarded_messages(source_chat_id, source_message_id);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_monitored_groups_chat_id
    ON monitored_groups(chat_id);

CREATE INDEX IF NOT EXISTS idx_monitored_groups_enabled
    ON monitored_groups(enabled);
"""
