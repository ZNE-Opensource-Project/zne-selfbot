# ZNE

A feature-rich Discord selfbot built on `discord.py-self` with a built-in WebUI, command execution, live logs, and message logging.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [venv](#venv)
  - [uv (optional)](#uv-optional)
- [Configuration](#configuration)
- [WebUI](#webui)
- [Cogs & Commands](#cogs--commands)
- [Database](#database)
- [Disclaimer](#disclaimer)

## Features

- Selfbot and userbot mode support
- Onboarding wizard (auto-generates `config.py`)
- Prefix-based commands loaded from cogs
- Built-in paginated help system
- `aiosqlite` message logging
- Flask WebUI at `http://127.0.0.1:5000`
- Live console log streaming via SSE
- Command execution from the web dashboard
- Stats endpoint with uptime tracking

### WebUI

The WebUI runs on a daemon Flask thread on **port 5000**. It exposes:

- `/` - Dashboard
- `/commands` - Command catalog grouped by cog
- `/api/command/<name>` - Command metadata
- `/api/execute` - Execute commands from the web
- `/stats` - Bot stats (username, guilds, command count, uptime, version)
- `/api/logs` - Recent console logs
- `/stream` - Live log SSE stream

## Prerequisites

- Python 3.10+
- Discord token

## Setup

### venv

```powershell
# Create a virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### uv (optional)

```powershell
# Create a virtual environment
uv venv

# Activate it
.\venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt

# Run
python main.py
```

## Configuration

If no valid `config.py` is found, ZNE runs an onboarding wizard:

```python
class BOT:
    TOKEN = "..."
    PREFIX = "."
    BOT_TYPE = "self"
```

`BOT_TYPE` accepts `"self"` or `"user"`.

## Cogs & Commands

Loaded automatically from `core/` and `cogs/`.

| Cog | Description |
|------|-------------|
| Admin | Channel management, moderation, server info, webhooks, user info |
| Animation | ASCII animations, countdowns, custom animations |
| Dump | Channel/server dumps (images, videos, text, members, emojis, stickers) |
| Encode | Hash, base encoding, AES encrypt/decrypt, URL/Morse/etc. |
| Fun | Games, facts, jokes, math, roleplay actions |
| Help | Paginated reaction-based help |
| Text | Text manipulation (zalgo, leet, emojify, flip, etc.) |

Use `.help` in Discord to browse.

## Database

`aiosqlite` stores data in `zne.db`:

- `zne_meta` - schema version tracking
- `message_log` - guild_id, channel_id, author_id, content, timestamp

## Disclaimer

Using selfbots violates Discord ToS. Use at your own risk.
