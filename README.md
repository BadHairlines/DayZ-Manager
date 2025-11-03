# DayZ Manager

A Discord bot for DayZ servers that lets admins manage **map flags**, **factions**, and **member roles** with slick embeds, persistent UI views, and Postgres-backed state. 🧭🏴

## ✨ Features

- **Interactive Flag Panel**  
  Persistent message with buttons/selects to **assign** and **release** flags per map.
- **Slash Commands for Admins**  
  `/setup`, `/assign`, `/release`, `/create-faction`, `/delete-faction`, `/add-member`, `/remove-member`
- **Faction System**  
  Auto-creates faction **roles**, private **HQ channels**, assigns colors, and tracks **members & leader**.
- **Map-Aware Logging**  
  Per-map logs (e.g. `#factions-livonia-logs`) and general action logs with rich embeds.
- **Auto-Refresh on Startup**  
  Safely refreshes flag embeds for every configured map in each guild.
- **Error Handling**  
  Clean, user-friendly error embeds + optional `#bot-errors` channel.
- **PostgreSQL Storage**  
  Durable storage for flags, message locations, and factions.

---

## 🧱 Requirements

- **Python** 3.10+
- **Discord Bot** with Privileged Intents enabled:
  - Server Members
  - Message Content (if you use text commands)
- **PostgreSQL** 12+ (or managed Postgres on Railway/Render/etc.)

---

## 🚀 Quick Start

```bash
# 1) Install deps
pip install -r requirements.txt

# 2) Export env vars (see .env example below)
export DISCORD_TOKEN=your_bot_token
export DATABASE_URL=postgres://user:pass@host:5432/dbname

# 3) Run the bot
python -m dayz_manager.bot
