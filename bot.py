import os
import asyncio
import logging
import discord
from discord.ext import commands
from cogs.utils import init_db, cleanup_deleted_roles, db_pool
from cogs.assign import FlagManageView  # ✅ persistent view class

# =========================
# 🧩 Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s]: %(message)s",
    datefmt="%H:%M:%S"
)

# =========================
# ⚙️ Discord Bot Setup
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.guild_reactions = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False


# =========================
# 🚀 Bot Events
# =========================
@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # ✅ Sync slash commands only once
    if not bot.synced:
        try:
            synced = await bot.tree.sync()
            bot.synced = True
            logging.info(f"✅ Synced {len(synced)} slash commands with Discord.")
        except Exception as e:
            logging.error(f"⚠️ Failed to sync slash commands: {e}")
    else:
        logging.info("⏭️ Slash commands already synced, skipping.")

    # ✅ Auto-cleanup deleted roles
    try:
        for guild in bot.guilds:
            await cleanup_deleted_roles(guild)
            await asyncio.sleep(1)
        logging.info("🧹 Auto-cleanup complete for all guilds.")
    except Exception as e:
        logging.error(f"⚠️ Auto-cleanup failed: {e}")

    logging.info("------")


# =========================
# 🔧 Dynamic Cog Loader
# =========================
async def load_cogs():
    for root, _, files in os.walk("cogs"):
        if "helpers" in root:
            continue
        for filename in files:
            if filename.endswith(".py") and not filename.startswith("__") and filename != "utils.py":
                cog_path = os.path.join(root, filename).replace(os.sep, ".")[:-3]
                try:
                    await bot.load_extension(cog_path)
                    logging.info(f"✅ Loaded cog: {cog_path}")
                except Exception as e:
                    logging.error(f"❌ Failed to load {cog_path}: {e}")


# =========================
# 🔁 Persistent View Registration
# =========================
async def register_persistent_views(bot: commands.Bot):
    """Re-register all FlagManageView UIs after restart."""
    from cogs.utils import db_pool  # make sure we use the global one

    # Defensive check to avoid NoneType errors
    if db_pool is None:
        logging.warning("⚠️ Database not initialized yet. Skipping persistent view registration.")
        return

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT guild_id, map, message_id FROM flag_messages;")
    except Exception as e:
        logging.error(f"❌ Could not fetch flag_messages: {e}")
        return

    for row in rows:
        guild = bot.get_guild(int(row["guild_id"]))
        if not guild:
            continue

        try:
            view = FlagManageView(guild, row["map"], "N/A", bot)
            bot.add_view(view, message_id=int(row["message_id"]))
            logging.info(f"✅ Registered persistent view for {guild.name} ({row['map']})")
        except Exception as e:
            logging.warning(f"⚠️ Failed to register persistent view for {guild.name}: {e}")

    logging.info(f"🔄 Persistent view registration complete for {len(rows)} entries.")


# =========================
# 🧩 Main Async Runner
# =========================
async def main():
    await asyncio.sleep(5)
    async with bot:
        await init_db()  # ✅ must be first to create db_pool
        await load_cogs()
        await register_persistent_views(bot)  # ✅ now safe to call

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("❌ DISCORD_TOKEN not set in environment variables.")

        for attempt in range(3):
            try:
                await bot.start(token)
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    wait_time = 60 * (attempt + 1)
                    logging.warning(f"⚠️ Rate-limited by Discord. Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Bot manually stopped.")
