import os
import asyncio
import logging
import discord
from discord.ext import commands
from cogs.utils import init_db, cleanup_deleted_roles, db_pool
from cogs.assign import FlagManageView  # ✅ Import the persistent view class

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
bot.synced = False  # ✅ prevent multiple slash syncs


# =========================
# 🚀 Bot Events
# =========================
@bot.event
async def on_ready():
    """Triggered when the bot successfully connects."""
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
            await asyncio.sleep(1)  # gentle pacing between guilds
        logging.info("🧹 Auto-cleanup complete for all guilds.")
    except Exception as e:
        logging.error(f"⚠️ Auto-cleanup failed: {e}")

    logging.info("------")


# =========================
# 🔧 Dynamic Cog Loader
# =========================
async def load_cogs():
    """Auto-load all valid cogs in the cogs directory (skips helpers)."""
    for root, _, files in os.walk("cogs"):
        if "helpers" in root:
            continue  # 🚫 Skip helper modules

        for filename in files:
            if filename.endswith(".py") and not filename.startswith("__") and filename not in ["utils.py"]:
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
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT guild_id, map, message_id FROM flag_messages;")

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
# 🧩 Main Async Runner (Rate-limit safe)
# =========================
async def main():
    await asyncio.sleep(5)  # 🕒 grace delay before connecting to Discord
    async with bot:
        await init_db()          # connect PostgreSQL
        await load_cogs()        # load all cogs
        await register_persistent_views(bot)  # ✅ add this line

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("❌ DISCORD_TOKEN not set in environment variables.")

        # 🔁 Smart login retry if rate-limited
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
