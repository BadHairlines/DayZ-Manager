import os
import asyncio
import discord
from discord.ext import commands

from core.flags import init_db
from cogs.flag_system import FlagSystem


intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def startup():
    await init_db()


@bot.event
async def on_ready():
    print(f"[READY] Logged in as {bot.user}")


async def main():
    await startup()

    async with bot:
        await bot.add_cog(FlagSystem(bot))
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
