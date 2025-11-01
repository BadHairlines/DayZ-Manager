import os
import asyncio
import discord
import logging
from discord.ext import commands
from cogs.utils import init_db  # ✅ PostgreSQL connection setup

# ──────────────────────────────────────────────
# 🪖 DAYZ MANAGER - SYSTEM BOOT SEQUENCE
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ──────────────────────────────────────────────
# 📡 SYSTEM STARTUP EVENT
# ──────────────────────────────────────────────
@bot.event
async def on_ready():
    """Triggered when the bot successfully connects to Discord."""
    print("""
──────────────────────────────────────────────
🪖  DAYZ MANAGER SYSTEM ONLINE
──────────────────────────────────────────────
⚙️   Initializing command modules...
📡   Establishing field communications...
──────────────────────────────────────────────
""")
    try:
        synced = await bot.tree.sync()
        print(f"✅  Synced {len(synced)} slash commands successfully.")
    except Exception as e:
        print(f"⚠️  Command sync failed: {e}")

    print(f"🎖️  Connected as {bot.user} | Operating in {len(bot.guilds)} guild(s)")
    print("──────────────────────────────────────────────\n")


# ──────────────────────────────────────────────
# 🧩 LOAD ALL COMMAND MODULES (COGS)
# ──────────────────────────────────────────────
async def load_cogs():
    """Load mission-critical modules dynamically."""
    cogs = [
        "cogs.activity_check",
        "cogs.assign",
        "cogs.factions",
        "cogs.flags",
        "cogs.mention_category",
        "cogs.release",
        "cogs.reset",
        "cogs.setup",
        "cogs.setup_emojis"
    ]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logging.info(f"✅  Loaded module: {cog}")
        except Exception as e:
            logging.error(f"❌  Failed to load {cog}: {e}")


# ──────────────────────────────────────────────
# 🚀 MAIN BOOT LOGIC
# ──────────────────────────────────────────────
async def main():
    async with bot:
        print("⚙️  Connecting to PostgreSQL database...")
        await init_db()

        print("🧭  Deploying operational modules...")
        await load_cogs()

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("❌  DISCORD_TOKEN missing from Railway environment variables!")

        print("""
──────────────────────────────────────────────
✅  All systems operational — deploying DayZ Manager...
──────────────────────────────────────────────
""")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
