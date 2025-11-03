# DayZ Manager

Run locally:
```bash
python -m dayz_manager.bot
```

Environment:
- `DISCORD_TOKEN` (required)
- `DATABASE_URL` (or `POSTGRES_URL` or `PG_URL`)

Project layout follows:

```
dayz_manager/
  bot.py
  config.py
  cogs/
    helpers/
    flags/
    factions/
    utils/
tests/
requirements.txt
pyproject.toml
```
