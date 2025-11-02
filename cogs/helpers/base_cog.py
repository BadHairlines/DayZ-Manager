import discord
from cogs.utils import db_pool, create_flag_embed

class BaseCog:
    """Reusable helper methods shared across all cogs."""

    def make_embed(self, title: str, desc: str, color: int, author_icon: str, author_name: str) -> discord.Embed:
        """Consistent embed styling."""
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=f"{author_icon} {author_name}")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def update_flag_message(self, guild: discord.Guild, guild_id: str, map_key: str):
        """Refresh the live flag message safely."""
        # ✅ Safety: database might not be ready yet
        if db_pool is None:
            print("⚠️ [BaseCog] Database pool not initialized — skipping flag message update.")
            return

        # ✅ Try to acquire DB connection
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id, map_key
                )
        except Exception as e:
            print(f"⚠️ [BaseCog] Database query failed: {e}")
            return

        if not row:
            print(f"⚠️ [BaseCog] No flag message found for guild={guild_id}, map={map_key}")
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            print(f"⚠️ [BaseCog] Channel not found for map={map_key}")
            return

        # ✅ Try to edit the flag message
        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
            print(f"✅ [BaseCog] Flag message updated for {guild.name} ({map_key})")
        except Exception as e:
            print(f"⚠️ [BaseCog] Failed to update flag message: {e}")
