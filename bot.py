import os
import asyncio
import discord
from discord.ext import commands
from cogs.utils import init_db  # ✅ Import PostgreSQL init
# (No more load_data, since JSON is replaced)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Triggered when the bot successfully connects to Discord."""
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # ✅ Sync all slash commands after bot is ready
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands with Discord.")
    except Exception as e:
        print(f"⚠️ Failed to sync slash commands: {e}")

    print("------")


async def load_cogs():
    """Load bot cogs dynamically."""
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
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"❌ Failed to load {cog}: {e}")


async def main():
    async with bot:
        # ✅ Connect to PostgreSQL
        await init_db()

        # ✅ Load all cogs after DB is ready
        await load_cogs()

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("❌ DISCORD_TOKEN not set in Railway environment variables.")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
