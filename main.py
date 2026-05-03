I'll produce drop-in replacements for every file. Writing them in parallel to `/app/patched/` mirroring the original structure so you can copy them straight in.
Action: file_editor create /app/patched/main.py --file-text "import os
import asyncio
import importlib
import logging

import discord
from discord.ext import commands

from cogs import utils

log = logging.getLogger(\"dayz-manager\")
logging.basicConfig(level=logging.INFO, format=\"%(asctime)s [%(levelname)s] %(name)s: %(message)s\")

# -----------------------------
# BOT SETUP
# -----------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix=\"!\", intents=intents)
bot.synced = False


# -----------------------------
# DATABASE INIT
# -----------------------------
async def init_db():
    await utils.ensure_connection()
    log.info(\"[DB] Connected\")


# -----------------------------
# COG LOADING
# -----------------------------
SKIP_FILES = {\"__init__.py\", \"utils.py\", \"ui_views.py\", \"flag_manager.py\"}
SKIP_DIRS = {\"helpers\", \"__pycache__\"}
COG_FOLDERS = [\"cogs\", \"misc\"]


async def load_cogs():
    loaded = 0

    for folder in COG_FOLDERS:
        if not os.path.isdir(folder):
            continue

        for root, dirs, files in os.walk(folder):
            # prune skipped directories in-place so os.walk doesn't descend into them
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for file in files:
                if file in SKIP_FILES or not file.endswith(\".py\") or file.startswith(\"_\"):
                    continue

                module = os.path.join(root, file).replace(os.sep, \".\")[:-3]

                # only load modules that actually expose a `setup` coroutine
                try:
                    mod = importlib.import_module(module)
                except Exception as e:
                    log.error(f\"[COG IMPORT ERROR] {module}: {e}\")
                    continue

                if not hasattr(mod, \"setup\"):
                    continue

                try:
                    await bot.load_extension(module)
                    loaded += 1
                except Exception as e:
                    log.error(f\"[COG ERROR] {module}: {e}\")

    log.info(f\"[COGS] Loaded {loaded}\")


# -----------------------------
# READY EVENT
# -----------------------------
@bot.event
async def on_ready():
    if not bot.synced:
        try:
            dev_guild = os.getenv(\"DEV_GUILD_ID\")
            if dev_guild:
                guild_obj = discord.Object(id=int(dev_guild))
                bot.tree.copy_global_to(guild=guild_obj)
                await bot.tree.sync(guild=guild_obj)
                log.info(f\"[SYNC] Slash commands synced to guild {dev_guild}\")
            else:
                await bot.tree.sync()
                log.info(\"[SYNC] Slash commands synced globally\")
            bot.synced = True
        except Exception as e:
            log.error(f\"[SYNC ERROR] {e}\")

    log.info(f\"[READY] Logged in as {bot.user}\")


# -----------------------------
# STARTUP FLOW
# -----------------------------
async def startup():
    if not os.getenv(\"DATABASE_URL\"):
        raise RuntimeError(\"DATABASE_URL missing\")

    if not os.getenv(\"DISCORD_TOKEN\"):
        raise RuntimeError(\"DISCORD_TOKEN missing\")

    for attempt in range(5):
        try:
            await init_db()
            break
        except Exception as e:
            log.warning(f\"[DB RETRY {attempt + 1}] {e}\")
            await asyncio.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError(\"DB connection failed after retries\")

    await load_cogs()


# -----------------------------
# MAIN
# -----------------------------
async def main():
    await startup()

    token = os.getenv(\"DISCORD_TOKEN\")

    try:
        async with bot:
            await bot.start(token)
    finally:
        await utils.close_db()
        log.info(\"[DB] Pool closed\")


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == \"__main__\":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info(\"Shutdown requested\")
"
Observation: Create successful: /app/patched/main.py
