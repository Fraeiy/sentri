# TG Admin Watch

[![CI](https://github.com/fraeiy/tg-admin-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/fraeiy/tg-admin-watch/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

Monitor selected Telegram groups and automatically forward messages from chosen users (admins or manually selected members) to a destination chat — preserving media, captions, and formatting.

**Uses your personal Telegram account** via [Telethon](https://docs.telethon.dev/) (not the Bot API), so you can monitor any group you are a member of.

## Features

- **User ID matching** — Users are stored and matched by immutable Telegram user IDs, not usernames
- **Flexible watch modes** — Watch admins only, selected users, or both
- **Media preservation** — Forwards photos, videos, voice notes, documents, and captions
- **Duplicate prevention** — Tracks forwarded messages in SQLite to avoid re-sending
- **Auto-reconnect** — Recovers automatically after network interruptions
- **Rate limit handling** — Graceful backoff on Telegram flood waits
- **Interactive CLI** — Rich terminal UI for managing groups and users
- **Extensible architecture** — Notification backend port ready for Discord, Slack, Email, ntfy, webhooks

## Requirements

- Python 3.12 or newer
- A [Telegram API application](https://my.telegram.org/apps) (`api_id` + `api_hash`)
- A personal Telegram account

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/fraeiy/tg-admin-watch.git
cd tg-admin-watch
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS / Termux
source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and set your Telegram API credentials:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
```

### 3. Authenticate

```bash
tg-admin-watch auth
```

Enter your phone number, verification code, and 2FA password if enabled. A session file is saved to `./data/session.session`.

### 4. Configure monitoring

```bash
# Interactive menu (recommended for first-time setup)
tg-admin-watch interactive

# Or use individual commands:
tg-admin-watch config set-destination   # Where to forward messages
tg-admin-watch groups add               # Add a group to monitor
tg-admin-watch users add                # Add users to watch (by user ID)
tg-admin-watch users sync-admins        # Auto-discover group admins
```

### 5. Start watching

```bash
tg-admin-watch watch
```

Press `Ctrl+C` to stop.

## Installation by Platform

### Windows

```powershell
# Install Python 3.12+ from https://www.python.org/downloads/
# Ensure "Add Python to PATH" is checked during installation

git clone https://github.com/fraeiy/tg-admin-watch.git
cd tg-admin-watch
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

copy .env.example .env
# Edit .env with your API credentials

tg-admin-watch auth
tg-admin-watch interactive
```

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv git

git clone https://github.com/fraeiy/tg-admin-watch.git
cd tg-admin-watch
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
nano .env  # Set API credentials

tg-admin-watch auth
tg-admin-watch interactive
```

### macOS

```bash
# Install Python via Homebrew
brew install python@3.12 git

git clone https://github.com/fraeiy/tg-admin-watch.git
cd tg-admin-watch
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your API credentials

tg-admin-watch auth
tg-admin-watch interactive
```

### Android (Termux)

```bash
pkg update && pkg upgrade
pkg install python git

git clone https://github.com/fraeiy/tg-admin-watch.git
cd tg-admin-watch
python -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
nano .env  # Set API credentials

tg-admin-watch auth
tg-admin-watch interactive

# Run in background with tmux:
pkg install tmux
tmux new -s tgwatch
tg-admin-watch watch
# Detach: Ctrl+B then D
```

> **Termux note:** Keep Termux alive in the background (disable battery optimization for Termux) so the watcher stays connected.

## CLI Reference

| Command | Description |
|---------|-------------|
| `tg-admin-watch auth` | Authenticate with Telegram |
| `tg-admin-watch watch` | Start monitoring and forwarding |
| `tg-admin-watch status` | Show configuration summary |
| `tg-admin-watch interactive` | Launch interactive menu |
| `tg-admin-watch groups list` | List monitored groups |
| `tg-admin-watch groups add` | Add a group interactively |
| `tg-admin-watch groups enable <id>` | Enable a group |
| `tg-admin-watch groups disable <id>` | Disable a group |
| `tg-admin-watch groups edit <id>` | Edit group settings |
| `tg-admin-watch groups remove <id>` | Remove a group |
| `tg-admin-watch users list <group_id>` | List watched users |
| `tg-admin-watch users add <group_id>` | Add a user (matched by ID) |
| `tg-admin-watch users sync-admins <group_id>` | Sync admin users from Telegram |
| `tg-admin-watch users remove <id>` | Remove a watched user |
| `tg-admin-watch config set-destination` | Set global forward destination |
| `tg-admin-watch config show` | Show all configuration |

### Watch Modes

| Mode | Behavior |
|------|----------|
| `selected_users` | Forward only manually added users |
| `admins_only` | Forward all group admins |
| `admins_and_selected` | Forward admins plus manually added users |

## User ID Matching

Usernames on Telegram can change at any time. TG Admin Watch stores and matches users by their **immutable numeric user ID** internally. The CLI displays usernames and display names for convenience, but all matching logic uses `user_id`.

```
CLI display:  Alice Smith · @alice · id:123456789
Internal key: user_id = 123456789
```

## Docker

```bash
# Build
docker compose build

# Authenticate (interactive, one-time)
docker compose run --rm tg-admin-watch auth

# Configure (interactive)
docker compose run --rm tg-admin-watch interactive

# Start watching
docker compose up -d

# View logs
docker compose logs -f
```

Data (session, database, logs) is persisted in the `tg-data` Docker volume.

## Architecture

```
src/tg_admin_watch/
├── cli/                    # Typer CLI + Rich UI
├── config/                 # Pydantic settings
├── core/
│   ├── models.py           # Domain models
│   ├── ports.py            # Interfaces (repositories, notification backends)
│   └── services/           # Business logic (MonitorService)
├── infrastructure/
│   ├── database/           # SQLite repository
│   ├── telegram/           # Telethon client, events, formatter
│   └── notifications/      # Notification backends (Telegram, future: Discord, etc.)
└── utils/                  # Logging, rate limiting
```

The codebase follows **clean architecture** principles:

- **Core** contains business logic and abstract ports — no Telethon or SQLite imports
- **Infrastructure** implements ports with concrete adapters
- **Notification backends** implement `BaseNotificationBackend` and register via `NotificationRegistry`

### Adding a New Notification Backend

```python
from tg_admin_watch.infrastructure.notifications.base import (
    BaseNotificationBackend,
    notification_registry,
)

class DiscordBackend(BaseNotificationBackend):
    @property
    def name(self) -> str:
        return "discord"

    async def send_text(self, text: str, *, destination: int | str) -> int | str:
        # Send to Discord webhook/channel
        ...

    async def send_media(self, media, *, caption, destination) -> int | str:
        ...

notification_registry.register("discord", DiscordBackend)
```

## Configuration

All configuration is stored in SQLite (`./data/tg_admin_watch.db` by default). Environment variables control runtime settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_API_ID` | *(required)* | Telegram API ID |
| `TELEGRAM_API_HASH` | *(required)* | Telegram API hash |
| `TG_ADMIN_WATCH_DATA_DIR` | `./data` | Data directory |
| `TG_ADMIN_WATCH_LOG_LEVEL` | `INFO` | Log level |
| `TG_ADMIN_WATCH_RECONNECT_MAX_DELAY` | `300` | Max reconnect delay (seconds) |
| `TG_ADMIN_WATCH_RATE_LIMIT_MAX_RETRIES` | `5` | Max rate limit retries |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src tests
ruff format src tests

# Type check
mypy src/tg_admin_watch --ignore-missing-imports
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure `ruff check` and `pytest` pass
5. Submit a pull request

## License

MIT License — see [LICENSE](LICENSE) for details.

## Disclaimer

This tool uses the Telegram Client API with your personal account. Use responsibly and in compliance with [Telegram's Terms of Service](https://telegram.org/tos). The authors are not responsible for any account restrictions resulting from misuse.