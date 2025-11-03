import os
import asyncio
import logging
import importlib
import discord
from discord.ext import commands
from cogs import utils

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
    """Safely import the FlagManageView class."""
    try:
        mod = importlib.import_module("cogs.ui_views")
        return getattr(mod, "FlagManageView", None)
    except Exception as e:
        log.warning(f"⚠️ Could not load FlagManageView: {e}")
        return None


async def register_persistent_views():
    """Re-register saved flag panels for all guilds/maps."""
    FlagManageView = resolve_flag_manage_view()
    if not FlagManageView or utils.db_pool is None:
        return

    async with utils.db_pool.acquire() as conn:
        try:
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
SKIP_FILES = {"__init__.py", "utils.py", "faction_utils.py", "ui_views.py"}

async def load_cogs():
    loaded = 0
    for root, dirs, files in os.walk("cogs"):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "helpers")]
        for filename in files:
            if not filename.endswith(".py") or filename in SKIP_FILES or filename.startswith("_"):
                continue
            module_path = os.path.join(root, filename).replace(os.sep, ".")[:-3]
            try:
                await bot.load_extension(module_path)
                log.info(f"✅ Loaded cog: {module_path}")
                loaded += 1
            except Exception as e:
                log.error(f"❌ Failed to load {module_path}: {e}")
    log.info(f"📦 Total cogs loaded: {loaded}")


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

    if utils.db_pool is None:
        log.error("❌ Database not connected!")

    await register_persistent_views()
    log.info("------ Ready ------")


# =========================
# 🚀 Main
# =========================
async def main():
    await asyncio.sleep(1)  # small Railway delay
    await utils.init_db()
    await load_cogs()

    token = os.getenv("DISCORD_TOKEN")
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
