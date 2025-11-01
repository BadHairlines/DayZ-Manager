import os
import asyncio
import discord
from discord.ext import commands
from cogs.utils import load_data

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# === Load server data ===
load_data()


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


async def load_cogs():
    """Load bot cogs dynamically."""
    cogs = [
        "cogs.setup",
        "cogs.flags",
        "cogs.assign"   # ✅ Added assign cog
    ]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"❌ Failed to load {cog}: {e}")


async def main():
    async with bot:
        await load_cogs()
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError("❌ DISCORD_TOKEN not set in Railway environment variables.")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
