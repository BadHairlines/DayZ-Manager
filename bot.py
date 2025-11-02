import os
import asyncio
import logging
import importlib
import discord
from discord.ext import commands

# ✅ Shared utilities (DB, helpers)
from cogs import utils  # make sure cogs/__init__.py exists (can be empty)

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
# 🤖 Discord Bot
# =========================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.guild_messages = True
intents.message_content = True
intents.guild_reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False  # track slash sync once


# =========================
# 🔁 Persistent Views
# =========================
def resolve_flag_manage_view():
    """
    Try to import FlagManageView from where your project defines it.
    Prefer cogs.ui_views.FlagManageView; fallback to cogs.assign.FlagManageView.
    """
    for path, cls in (("cogs.ui_views", "FlagManageView"), ("cogs.assign", "FlagManageView")):
        try:
            mod = importlib.import_module(path)
            view_cls = getattr(mod, cls, None)
            if view_cls:
                log.info(f"✅ Using {cls} from {path}")
                return view_cls
        except Exception as e:
            log.debug(f"FlagManageView not found in {path}: {e}")
    log.warning("⚠️ FlagManageView not available — persistent views will be skipped.")
    return None


async def register_persistent_views():
    """Re-register all saved FlagManageView panels for each guild/map."""
    FlagManageView = resolve_flag_manage_view()
    if FlagManageView is None:
        return

    if utils.db_pool is None:
        log.warning("⚠️ DB not initialized; skipping persistent view registration.")
        return

    async with utils.db_pool.acquire() as conn:
        try:
            rows = await conn.fetch("SELECT guild_id, map, message_id FROM flag_messages;")
        except Exception as e:
            log.info(f"ℹ️ No flag_messages table yet (or query failed): {e}")
            return

    registered = 0
    for row in rows:
        guild = bot.get_guild(int(row["guild_id"]))
        if not guild:
            continue
        try:
            view = FlagManageView(guild, row["map"], "N/A", bot)
            bot.add_view(view, message_id=int(row["message_id"]))
            registered += 1
        except Exception as e:
            log.warning(f"⚠️ Could not re-register view for guild {row['guild_id']} map {row['map']}: {e}")

    log.info(f"🔄 Persistent views registered: {registered}")


# =========================
# 📦 Cog Loader
# =========================
SKIP_FILES = {
    "__init__.py",
    "utils.py",          # helper (not a cog)
    "faction_utils.py",  # helper (not a cog)
    "ui_views.py",       # UI components (not a cog)
}

async def load_cogs():
    """Walk ./cogs and load every cog except helper-only modules."""
    loaded = 0
    for root, dirs, files in os.walk("cogs"):
        # ignore cache folders and helper modules
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "helpers")]

        for filename in files:
            if not filename.endswith(".py"):
                continue
            if filename in SKIP_FILES or filename.startswith("_"):
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

    # One-time slash sync
    if not bot.synced:
        try:
            synced = await bot.tree.sync()
            bot.synced = True
            log.info(f"✅ Synced {len(synced)} slash command(s).")
        except Exception as e:
            log.error(f"⚠️ Failed to sync slash commands: {e}")

    if utils.db_pool is None:
        log.error("❌ Database not connected! Commands touching DB will fail.")

    # Re-register persistent views (safe even if none exist)
    await register_persistent_views()

    log.info("------")


# =========================
# 🛠️ Owner-only helpers
# =========================
@bot.command(name="sync", help="Owner: force re-sync slash commands.")
@commands.is_owner()
async def _sync(ctx: commands.Context):
    cmds = await bot.tree.sync()
    await ctx.send(f"✅ Slash commands synced: {len(cmds)}")


# =========================
# 🚀 Main
# =========================
async def main():
    # Small delay to ensure env is ready (Railway/containers) before DB connect
    await asyncio.sleep(1)

    # ✅ Initialize DB first
    await utils.init_db()

    # ✅ Load all cogs
    await load_cogs()

    # ✅ (Optional) Pre-register FlagManageView to remove warning
    try:
        from cogs.ui_views import FlagManageView
        bot.add_view(FlagManageView())
        log.info("✅ Pre-registered FlagManageView for persistent buttons.")
    except Exception:
        log.warning("⚠️ Could not pre-register FlagManageView (optional).")

    # ✅ Start bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("❌ DISCORD_TOKEN not set in environment.")

    async with bot:
        for attempt in range(3):
            try:
                await bot.start(token)
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    backoff = 30 * (attempt + 1)
                    log.warning(f"⚠️ Rate limited by Discord. Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🛑 Bot manually stopped.")
