import os
import asyncio
import logging
import importlib
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs import utils

# ==============================
# 📜 Logging setup
# ==============================
load_dotenv()  # allow local .env usage

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s]: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dayz-manager")

# ==============================
# 🤖 Bot setup
# ==============================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False

# ==============================
# ⚙️ Cog loader
# ==============================
SKIP_FILES = {"__init__.py", "utils.py", "faction_utils.py", "ui_views.py"}

async def load_cogs():
    """Dynamically load all non-helper cogs."""
    loaded = 0
    for root, dirs, files in os.walk("cogs"):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "helpers")]
        for file in files:
            if not file.endswith(".py") or file in SKIP_FILES or file.startswith("_"):
                continue
            module = os.path.join(root, file).replace(os.sep, ".")[:-3]
            try:
                await bot.load_extension(module)
                log.info(f"Loaded cog: {module}")
                loaded += 1
            except Exception as e:
                log.error(f"Failed to load {module}: {e}")
    log.info(f"✅ Total cogs loaded: {loaded}")

# ==============================
# 🧱 Helpers
# ==============================
def resolve_flag_manage_view():
    try:
        mod = importlib.import_module("cogs.ui_views")
        return getattr(mod, "FlagManageView", None)
    except Exception as e:
        log.warning(f"Could not import FlagManageView: {e}")
        return None

async def register_persistent_views():
    """Re-register persistent flag views after restart."""
    await utils.ensure_connection()

    FlagManageView = resolve_flag_manage_view()
    if not FlagManageView or utils.db_pool is None:
        log.warning("Cannot register persistent views — missing FlagManageView or DB pool.")
        return

    async with utils.safe_acquire() as conn:
        try:
            rows = await conn.fetch("SELECT guild_id, map, channel_id, message_id FROM flag_messages;")
        except Exception as e:
            log.info(f"No flag_messages table yet: {e}")
            return

    if not rows:
        log.info("No persistent flag views found.")
        return

    count = 0
    for r in rows:
        guild = bot.get_guild(int(r["guild_id"]))
        if not guild:
            continue
        channel = guild.get_channel(int(r["channel_id"]))
        if not channel:
            continue

        try:
            msg = await channel.fetch_message(int(r["message_id"]))
            view = FlagManageView(guild, r["map"], bot)
            bot.add_view(view, message_id=int(r["message_id"]))
            count += 1
        except Exception as e:
            log.warning(f"Could not re-register view for {guild.name}/{r['map']}: {e}")

    log.info(f"Re-registered {count} persistent views.")

# ==============================
# 🚀 Events
# ==============================
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    if not bot.synced:
        try:
            # use guild sync for testing; global sync for production
            if os.getenv("DEV_GUILD_ID"):
                gid = int(os.getenv("DEV_GUILD_ID"))
                cmds = await bot.tree.sync(guild=discord.Object(id=gid))
                log.info(f"Synced {len(cmds)} slash command(s) to guild {gid}.")
            else:
                cmds = await bot.tree.sync()
                log.info(f"Globally synced {len(cmds)} slash command(s).")
            bot.synced = True
        except Exception as e:
            log.error(f"Slash command sync failed: {e}")

    await register_persistent_views()
    log.info("✅ DayZ Manager Ready")

# ==============================
# ▶️ Entry Point
# ==============================
async def main():
    """Full startup with retry & graceful shutdown."""
    await asyncio.sleep(1)  # railway delay

    # Fix legacy postgres URL
    raw_dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("PG_URL")
    if raw_dsn and raw_dsn.startswith("postgres://"):
        os.environ["DATABASE_URL"] = raw_dsn.replace("postgres://", "postgresql://", 1)

    # --- connect DB with retries ---
    for attempt in range(5):
        try:
            await utils.ensure_connection()
            log.info("✅ Connected to database.")
            break
        except Exception as e:
            wait = 5 * (attempt + 1)
            log.warning(f"⚠️ DB connection failed ({attempt+1}/5): {e}")
            log.info(f"Retrying in {wait}s…")
            await asyncio.sleep(wait)
    else:
        raise RuntimeError("❌ Could not connect to database after 5 attempts.")

    await load_cogs()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set!")

    try:
        async with bot:
            await bot.start(token)
    except KeyboardInterrupt:
        log.info("🛑 Bot stopped manually.")
    finally:
        await utils.close_db()
        log.info("Database closed. Exiting cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
