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


## Setup management

Server administrators can manage their own guild-scoped flag setups:

- `/setups` — lists all saved flag setups in the current Discord server.
- `/deletesetup` — permanently deletes one setup after an administrator-only confirmation. It can also delete the setup channel and will only remove the category when that channel was the category's only channel.

Setup deletion is always restricted to the guild where the command is run. It removes the matching flags, stored message record, and that setup's audit history from PostgreSQL.

## Components V2 Flag Dashboard

The public Flag System now uses Discord Components V2 (`discord.py` 2.6+) instead of a traditional embed. Each setup has a persistent live dashboard with Claim Flag, Release Flag, View Flags, Find Flag, History, and Admin Panel controls. Existing classic flag messages are automatically replaced with the Components V2 dashboard during restoration. The official fixed flag registry remains unchanged; custom user-created flags are not supported.

## Live Flag Website

DayZ Manager now serves a read-only live flag portal from the same Railway service as the Discord bot.

Routes:
- `/flags?guild=<guild_id>&map=<map>&server=<server>` - live public flag page
- `/api/flags?guild=<guild_id>&map=<map>&server=<server>` - read-only JSON data
- `/health` - web health check

The Discord Components V2 flag dashboard automatically displays a **Live Website** link when a public base URL is available.

On Railway, generate a public domain for the DayZ Manager service. Railway supplies `RAILWAY_PUBLIC_DOMAIN` automatically. You may optionally override the generated link by setting `FLAG_WEB_BASE_URL` to a custom domain such as `https://flags.example.com`.

The web portal is read-only. Flag claims/releases still happen through Administrator-only Discord controls.
