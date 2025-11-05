import os
import asyncio
import logging
import importlib
import discord
from discord.ext import commands
from cogs import utils

# ==============================
# 📜 Logging setup
# ==============================
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
bot.synced = False  # track slash sync once


# ==============================
# 🧱 Helpers
# ==============================
def resolve_flag_manage_view():
    """Import FlagManageView safely."""
    try:
        mod = importlib.import_module("cogs.ui_views")
        return getattr(mod, "FlagManageView", None)
    except Exception as e:
        log.warning(f"Could not load FlagManageView: {e}")
        return None


async def _acquire_conn():
    """Acquire a DB connection, using safe_acquire() if available."""
    if hasattr(utils, "safe_acquire"):
        return utils.safe_acquire()

    class _PoolCtx:
        def __init__(self, pool):
            self.pool = pool
            self.conn = None
        async def __aenter__(self):
            await utils.ensure_connection()
            self.conn = await self.pool.acquire()
            return self.conn
        async def __aexit__(self, exc_type, exc, tb):
            if self.conn:
                await self.pool.release(self.conn)
    return _PoolCtx(utils.db_pool)


async def register_persistent_views():
    """Re-register saved flag panels for all guilds/maps."""
    await utils.ensure_connection()

    FlagManageView = resolve_flag_manage_view()
    if not FlagManageView or utils.db_pool is None:
        log.warning("Cannot register persistent views — missing FlagManageView or DB pool.")
        return

    async with await _acquire_conn() as conn:
        try:
            rows = await conn.fetch("SELECT guild_id, map, channel_id, message_id FROM flag_messages;")
        except Exception as e:
            log.info(f"No flag_messages table yet: {e}")
            return

    if not rows:
        log.info("No flag messages found to re-register.")
        return

    count = 0
    for row in rows:
        guild_id = int(row["guild_id"])
        channel_id = int(row["channel_id"])
        message_id = int(row["message_id"])
        map_key = row["map"]

        guild = bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild {guild_id} not found; skipping.")
            continue

        channel = guild.get_channel(channel_id)
        if not channel:
            log.warning(f"Channel {channel_id} missing for {guild.name}/{map_key}; skipping.")
            continue

        try:
            msg = await channel.fetch_message(message_id)
            if not msg:
                log.warning(f"Message {message_id} not found in {guild.name}/{map_key}.")
                continue

            view = FlagManageView(guild, map_key, bot)
            bot.add_view(view, message_id=message_id)
            log.info(f"Re-registered view for {guild.name} → {map_key.title()}")
            count += 1

        except discord.NotFound:
            log.warning(f"Message {message_id} deleted in {guild.name}/{map_key}.")
        except Exception as e:
            log.warning(f"Failed to re-register view for {guild.name}/{map_key}: {e}")

    log.info(f"Persistent views registered: {count}")


# ==============================
# ⚙️ Cog loader
# ==============================
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
                log.info(f"Loaded cog: {module_path}")
                loaded += 1
            except Exception as e:
                log.error(f"Failed to load {module_path}: {e}")
    log.info(f"Total cogs loaded: {loaded}")


# ==============================
# 🚀 Events
# ==============================
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    if not bot.synced:
        try:
            dev_gid = os.getenv("DEV_GUILD_ID")
            if dev_gid:
                cmds = await bot.tree.sync(guild=discord.Object(id=int(dev_gid)))
                log.info(f"Synced {len(cmds)} slash command(s) to dev guild {dev_gid}.")
            else:
                cmds = await bot.tree.sync()
                log.info(f"Globally synced {len(cmds)} slash command(s).")
            bot.synced = True
        except Exception as e:
            log.error(f"Slash-sync failed: {e}")

    try:
        await utils.ensure_connection()
    except Exception as e:
        log.error(f"Database not connected! {e}")

    await asyncio.sleep(2)
    await register_persistent_views()
    log.info("Ready ✅")


# ==============================
# 🧠 Main entry
# ==============================
async def main():
    await asyncio.sleep(1)  # small Railway delay

    # --- Normalize DATABASE_URL ---
    raw_dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("PG_URL")
    if raw_dsn and raw_dsn.startswith("postgres://"):
        os.environ["DATABASE_URL"] = raw_dsn.replace("postgres://", "postgresql://", 1)

    # --- Retry DB connection ---
    for attempt in range(5):
        try:
            await utils.ensure_connection()
            log.info("✅ Connected to database.")
            break
        except Exception as e:
            wait = 5 * (attempt + 1)
            log.warning(f"⚠️ DB connection failed (attempt {attempt+1}/5): {e}")
            log.info(f"🔁 Retrying in {wait}s...")
            await asyncio.sleep(wait)
    else:
        raise RuntimeError("❌ Could not connect to Postgres after several retries.")

    await load_cogs()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set!")

    try:
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
    finally:
        if hasattr(utils, "close_db"):
            try:
                await utils.close_db()
                log.info("Database pool closed.")
            except Exception as e:
                log.warning(f"Failed to close database pool cleanly: {e}")


# ==============================
# ▶️ Entry point
# ==============================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot manually stopped.")
