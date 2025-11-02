import discord, asyncio
from discord.ext import commands
from cogs.utils import db_pool, MAP_DATA, create_flag_embed

class AutoRefresh(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_flag_message(self, guild: discord.Guild, map_key: str):
        guild_id = str(guild.id)
        if map_key not in MAP_DATA: return
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT channel_id,message_id FROM flag_messages WHERE guild_id=$1 AND map=$2", guild_id, map_key)
        if not row: return
        channel_id, message_id = int(row["channel_id"]), int(row["message_id"])
        channel = guild.get_channel(channel_id)
        if not channel:
            try:
                channel = await guild.create_text_channel(name=f"flags-{map_key}", reason=f"Recreated for {MAP_DATA[map_key]['name']} flags")
                await channel.send(f"This channel displays flag ownership for {MAP_DATA[map_key]['name']}.")
                async with db_pool.acquire() as conn:
                    await conn.execute("UPDATE flag_messages SET channel_id=$1 WHERE guild_id=$2 AND map=$3", str(channel.id), guild_id, map_key)
            except Exception: return
        embed = await create_flag_embed(guild_id, map_key)
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=embed)
        except discord.NotFound:
            msg = await channel.send(embed=embed)
            async with db_pool.acquire() as conn:
                await conn.execute("UPDATE flag_messages SET message_id=$1 WHERE guild_id=$2 AND map=$3", str(msg.id), guild_id, map_key)
        except discord.Forbidden:
            return
        except Exception:
            return

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        if getattr(self.bot, "_refresh_done", False): return
        self.bot._refresh_done = True
        await asyncio.sleep(5)
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            try:
                async with db_pool.acquire() as conn:
                    rows = await conn.fetch("SELECT map FROM flag_messages WHERE guild_id=$1", guild_id)
                if not rows: continue
                for row in rows:
                    await self.ensure_flag_message(guild, row["map"])
                    await asyncio.sleep(1)
            except Exception:
                continue

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
