import discord
from discord.ext import commands
from cogs.utils import db_pool, MAP_DATA, create_flag_embed
import asyncio

class AutoRefresh(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def update_flag_message(self, guild: discord.Guild, map_key: str):
        """Updates the existing flag message for a map if it exists."""
        guild_id = str(guild.id)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )

        if not row:
            return  # No message stored for this guild/map

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            return

        try:
            message = await channel.fetch_message(int(row["message_id"]))
            embed = await create_flag_embed(guild_id, map_key)
            await message.edit(embed=embed)
            print(f"🔄 Refreshed flags for {guild.name} - {MAP_DATA[map_key]['name']}")
        except Exception as e:
            print(f"⚠️ Failed to refresh flag message for {guild.name} ({map_key}): {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-refresh all stored flag messages after bot startup."""
        await self.bot.wait_until_ready()
        print("🚀 DayZ Manager starting flag auto-refresh...")

        # Small delay to ensure bot is fully connected
        await asyncio.sleep(5)

        for guild in self.bot.guilds:
            for map_key in MAP_DATA.keys():
                await self.update_flag_message(guild, map_key)
                await asyncio.sleep(1)  # avoid hitting rate limits

        print("✅ DayZ Manager has refreshed all stored flag messages successfully.")

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
