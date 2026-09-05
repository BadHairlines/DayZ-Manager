# DayZ Manager

Discord bot for The Hive's DayZ flag-management system plus utility cogs.

## Core commands

- `/setup` — create or repair a map/server flag board
- `/assign` — administrator flag assignment
- `/release` — administrator flag release
- `/flagstatus` — inspect a flag session, stored message, and missing roles
- `/flagrefresh` — force-refresh a public flag board and its persistent buttons
- `/flaghistory` — view recent audited claim/release actions
- `/botstatus` — check Discord/database health, latency, uptime, and command count
- `/teleporter` — generate two-way teleporter JSON files in approved guilds

## Flag UI

The public flag board keeps persistent Assign and Release buttons. Assign requires the user to have a role whose name starts with `Faction-`. Release requires Administrator permission. The role picker uses Discord's native role selector instead of a 25-role static dropdown.

The flag dropdown supports more than Discord's 25-option component limit by paging into additional choices when necessary.

## Supported maps

- Livonia
- Chernarus
- Sakhal
- Nasdara

## Database

PostgreSQL is required. Migrations run automatically at startup and preserve the existing `flags` and `flag_messages` data. The upgrade adds `flag_audit_log` for future claim/release history; no reset is required.

## Railway / environment

Required:

- `DISCORD_TOKEN`
- `DATABASE_URL`

Optional:

- `LOG_LEVEL` (default `INFO`)
- `DB_MAX_POOL_SIZE` (default `10`)

Install with `pip install -r requirements.txt` and start with `python main.py`.

Privileged Discord gateway intents remain disabled: Server Members and Message Content are not required by the current bot.
