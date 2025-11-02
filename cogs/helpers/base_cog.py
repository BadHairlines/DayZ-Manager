import discord
from cogs import utils

class BaseCog:
    def make_embed(self, title:str, desc:str, color:int, author_icon:str, author_name:str)->discord.Embed:
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=f"{author_icon} {author_name}")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def update_flag_message(self, guild:discord.Guild, guild_id:str, map_key:str):
        if utils.db_pool is None: return
        try:
            async with utils.db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT channel_id,message_id FROM flag_messages WHERE guild_id=$1 AND map=$2", guild_id, map_key)
            if not row: return
            channel = guild.get_channel(int(row["channel_id"]))
            if not channel: return
            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await utils.create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
        except Exception: return
