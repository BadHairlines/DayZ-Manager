import os
import asyncio
import logging
import discord
from discord.ext import commands
from cogs.utils import init_db, cleanup_deleted_roles

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


# =========================
# 🚀 Bot Events
# =========================
@bot.event
async def on_ready():
    """Triggered when the bot successfully connects."""
    logging.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logging.info(f"✅ Synced {len(synced)} slash commands with Discord.")
    except Exception as e:
        logging.error(f"⚠️ Failed to sync slash commands: {e}")

    # Auto-cleanup deleted roles
    try:
        for guild in bot.guilds:
            await cleanup_deleted_roles(guild)
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
        # 🚫 Skip the helpers directory completely
        if "helpers" in root:
            continue

        for filename in files:
            if filename.endswith(".py") and not filename.startswith("__") and filename not in ["utils.py"]:
                cog_path = os.path.join(root, filename).replace(os.sep, ".")[:-3]
                try:
                    await bot.load_extension(cog_path)
                    logging.info(f"✅ Loaded cog: {cog_path}")
                except Exception as e:
                    logging.error(f"❌ Failed to load {cog_path}: {e}")


# =========================
# 🧩 Main Async Runner
# =========================
async def main():
    async with bot:
        await init_db()  # Connect PostgreSQL
        await load_cogs()  # Load all cogs

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("❌ DISCORD_TOKEN not set in environment variables.")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
