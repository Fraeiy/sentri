# Sentri

[![CI](https://github.com/Fraeiy/sentri/actions/workflows/ci.yml/badge.svg)](https://github.com/Fraeiy/sentri/actions/workflows/ci.yml)
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
git clone https://github.com/Fraeiy/sentri.git
cd sentri
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
sentri auth
```

Enter your phone number, verification code, and 2FA password if enabled. A session file is saved to `./data/session.session`.

### 4. Configure monitoring

```bash
# Interactive menu (recommended for first-time setup)
sentri interactive

# Or use individual commands:
sentri config set-destination   # Where to forward messages
sentri groups add               # Add a group to monitor
sentri users add                # Add users to watch (by user ID)
sentri users sync-admins        # Auto-discover group admins
```

### 5. Start watching

```bash
sentri watch
```

Press `Ctrl+C` to stop.

## Web Dashboard

Sentri includes a browser-based UI that mirrors the CLI — manage groups, users, destination, authentication, and start/stop the watcher without the terminal.

### Install web dependencies

```bash
pip install -e ".[web]"
```

### Launch

```bash
sentri web
```

Open **http://127.0.0.1:8080** in your browser.

### Web features

- Dashboard with live status
- Telegram login (phone → code → 2FA)
- Add groups and users from Telegram dialogs
- Set destination chat
- Start/stop background watcher
- Sync group admins

### Web configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRI_WEB_HOST` | `127.0.0.1` | Bind address |
| `SENTRI_WEB_PORT` | `8080` | Bind port |
| `SENTRI_WEB_TOKEN` | *(none)* | Optional access token |

When `WEB_TOKEN` is set, append `?token=your_token` to the URL or send `Authorization: Bearer your_token`.

> **Security:** Bind to `127.0.0.1` by default. Only expose to your network with a `WEB_TOKEN` set.

## Installation by Platform

### Windows

```powershell
# Install Python 3.12+ from https://www.python.org/downloads/
# Ensure "Add Python to PATH" is checked during installation

git clone https://github.com/Fraeiy/sentri.git
cd sentri
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

copy .env.example .env
# Edit .env with your API credentials

sentri auth
sentri interactive
```

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv git

git clone https://github.com/Fraeiy/sentri.git
cd sentri
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
nano .env  # Set API credentials

sentri auth
sentri interactive
```

### macOS

```bash
# Install Python via Homebrew
brew install python@3.12 git

git clone https://github.com/Fraeiy/sentri.git
cd sentri
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your API credentials

sentri auth
sentri interactive
```

### Android (Termux)

```bash
pkg update && pkg upgrade
pkg install python git

git clone https://github.com/Fraeiy/sentri.git
cd sentri
python -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
nano .env  # Set API credentials

sentri auth
sentri interactive

# Run in background with tmux:
pkg install tmux
tmux new -s tgwatch
sentri watch
# Detach: Ctrl+B then D
```

> **Termux note:** Keep Termux alive in the background (disable battery optimization for Termux) so the watcher stays connected.

## CLI Reference

| Command | Description |
|---------|-------------|
| `sentri auth` | Authenticate with Telegram |
| `sentri watch` | Start monitoring and forwarding |
| `sentri web` | Launch the web dashboard |
| `sentri status` | Show configuration summary |
| `sentri interactive` | Launch interactive menu |
| `sentri groups list` | List monitored groups |
| `sentri groups add` | Add a group interactively |
| `sentri groups enable <id>` | Enable a group |
| `sentri groups disable <id>` | Disable a group |
| `sentri groups edit <id>` | Edit group settings |
| `sentri groups remove <id>` | Remove a group |
| `sentri users list <group_id>` | List watched users |
| `sentri users add <group_id>` | Add a user (matched by ID) |
| `sentri users sync-admins <group_id>` | Sync admin users from Telegram |
| `sentri users remove <id>` | Remove a watched user |
| `sentri config set-destination` | Set global forward destination |
| `sentri config show` | Show all configuration |

### Watch Modes

| Mode | Behavior |
|------|----------|
| `selected_users` | Forward only manually added users |
| `admins_only` | Forward all group admins |
| `admins_and_selected` | Forward admins plus manually added users |

## User ID Matching

Usernames on Telegram can change at any time. Sentri stores and matches users by their **immutable numeric user ID** internally. The CLI displays usernames and display names for convenience, but all matching logic uses `user_id`.

```
CLI display:  Alice Smith · @alice · id:123456789
Internal key: user_id = 123456789
```

## Docker

```bash
# Build
docker compose build

# Authenticate (interactive, one-time)
docker compose run --rm sentri auth

# Configure (interactive)
docker compose run --rm sentri interactive

# Start watching
docker compose up -d

# View logs
docker compose logs -f
```

Data (session, database, logs) is persisted in the `tg-data` Docker volume.

## Architecture

```
src/sentri/
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
from sentri.infrastructure.notifications.base import (
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

All configuration is stored in SQLite (`./data/sentri.db` by default). Environment variables control runtime settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_API_ID` | *(required)* | Telegram API ID |
| `TELEGRAM_API_HASH` | *(required)* | Telegram API hash |
| `SENTRI_DATA_DIR` | `./data` | Data directory |
| `SENTRI_LOG_LEVEL` | `INFO` | Log level |
| `SENTRI_RECONNECT_MAX_DELAY` | `300` | Max reconnect delay (seconds) |
| `SENTRI_RATE_LIMIT_MAX_RETRIES` | `5` | Max rate limit retries |

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
mypy src/sentri --ignore-missing-imports
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