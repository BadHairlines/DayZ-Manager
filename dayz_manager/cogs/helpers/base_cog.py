import discord
from dayz_manager.cogs.utils.database import create_flag_embed, db_pool

class BaseCog:
    """Reusable helper methods shared across all cogs."""

    def make_embed(self, title: str, desc: str, color: int, author_icon: str, author_name: str) -> discord.Embed:
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=f"{author_icon} {author_name}")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def update_flag_message(self, guild: discord.Guild, guild_id: str, map_key: str):
        """Refresh live flag message safely."""
        if db_pool is None:
            print("⚠️ Cannot update flag message — DB not initialized.")
            return

        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id, map_key
                )

            if not row:
                print(f"⚠️ No flag message entry found for map {map_key} in guild {guild.name}")
                return

            channel = guild.get_channel(int(row["channel_id"]))
            if not channel:
                print(f"⚠️ Channel missing for {map_key} in guild {guild.name}")
                return

            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
            print(f"✅ Flag display updated for {map_key} in {guild.name}")

        except Exception as e:
            print(f"❌ Failed to update flag message for {map_key}: {e}")
