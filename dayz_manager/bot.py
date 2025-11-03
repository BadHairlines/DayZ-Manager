import os
import asyncio
import logging
import importlib
import discord
from discord.ext import commands

from .config import DISCORD_TOKEN
from dayz_manager.cogs.utils.database import init_db, db_pool

# =========================
# 🧾 Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s]: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dayz-manager")

# =========================
# 🤖 Bot setup
# =========================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False  # track slash sync once

# =========================
# 🔁 Persistent Views
# =========================
def resolve_flag_manage_view():
    try:
        mod = importlib.import_module("dayz_manager.cogs.flags.ui")
        return getattr(mod, "FlagManageView", None)
    except Exception as e:
        log.warning(f"⚠️ Could not load FlagManageView: {e}")
        return None


async def register_persistent_views():
    FlagManageView = resolve_flag_manage_view()
    if not FlagManageView or db_pool is None:
        log.warning("⚠️ Skipping persistent view registration — DB not ready.")
        return

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT guild_id, map, message_id FROM flag_messages;")
    except Exception as e:
        log.info(f"ℹ️ No flag_messages table yet: {e}")
        return

    count = 0
    for row in rows:
        guild = bot.get_guild(int(row["guild_id"]))
        if not guild:
            continue
        try:
            view = FlagManageView(guild, row["map"], bot)
            bot.add_view(view, message_id=int(row["message_id"]))
            count += 1
        except Exception as e:
            log.warning(f"⚠️ Failed to re-register view for {row['guild_id']}:{row['map']} → {e}")

    log.info(f"🔄 Persistent views registered: {count}")

# =========================
# 📦 Cog Loader
# =========================
async def load_cogs():
    loaded = 0
    # Load helpers first so error handler is present
    for module_path in [
        "dayz_manager.cogs.helpers.error_handler",
        "dayz_manager.cogs.flags.setup",
        "dayz_manager.cogs.flags.assign",
        "dayz_manager.cogs.flags.release",
        "dayz_manager.cogs.factions.create",
        "dayz_manager.cogs.factions.delete",
        "dayz_manager.cogs.factions.members",
        "dayz_manager.cogs.flags.ui",  # view registration
        "dayz_manager.cogs.helpers.base_cog",  # not a cog, but keeps import sanity
    ]:
        try:
            await bot.load_extension(module_path)
            loaded += 1
            log.info(f"✅ Loaded cog: {module_path}")
        except Exception as e:
            log.warning(f"ℹ️ Skipped/non-cog or failed: {module_path} → {e}")

    log.info(f"📦 Total extensions attempted: {loaded}")

# =========================
# 🛰️ Events
# =========================
@bot.event
async def on_ready():
    log.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    if not bot.synced:
        try:
            cmds = await bot.tree.sync()
            bot.synced = True
            log.info(f"✅ Synced {len(cmds)} slash command(s).")
        except Exception as e:
            log.error(f"⚠️ Slash-sync failed: {e}")

    if db_pool is None:
        log.error("❌ Database not connected!")

    await register_persistent_views()
    log.info("------ Ready ------")

# =========================
# 🚀 Main
# =========================
async def main():
    await asyncio.sleep(1)  # small Railway delay
    await init_db()

    # ✅ Force reload so all cogs share the same initialized db_pool
    import sys
    from dayz_manager.cogs.utils import database as db_module
    sys.modules["dayz_manager.cogs.utils.database"] = db_module
    log.info(f"[DEBUG] Database module reloaded with pool: {db_module.db_pool}")

    await load_cogs()

    token = DISCORD_TOKEN
    if not token:
        raise RuntimeError("❌ DISCORD_TOKEN not set!")

    async with bot:
        for attempt in range(3):
            try:
                await bot.start(token)
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    wait = 30 * (attempt + 1)
                    log.warning(f"Rate limited, retrying in {wait}s…")
                    await asyncio.sleep(wait)
                else:
                    raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🛑 Bot manually stopped.")
