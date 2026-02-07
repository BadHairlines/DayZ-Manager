import logging
import discord
from cogs import utils
from cogs.ui_views import FlagManageView

log = logging.getLogger("dayz-manager")


class BaseCog:
    """Reusable base cog with embed helpers and message refresh support."""

    def make_embed(self, title: str, desc: str, color: int, author_icon: str, author_name: str) -> discord.Embed:
        """Create a standardized DayZ Manager embed."""
        if len(desc) > 4000:
            desc = desc[:3990] + "…"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=f"{author_icon} {author_name}")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def update_flag_message(self, guild: discord.Guild, guild_id: str, map_key: str) -> None:
        """Refresh the live flag message for a given map, including persistent view restoration."""
        try:
            await utils.ensure_connection()
        except Exception as e:
            log.warning(f"⚠️ Cannot update flag message — DB connection failed: {e}")
            return

        try:
            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id, map_key
                )

            if not row:
                log.info(f"⚠️ No flag message entry found for {map_key} in guild {guild.name}")
                return

            channel = guild.get_channel(int(row["channel_id"]))
            if not channel:
                log.warning(f"⚠️ Channel missing for {map_key} in guild {guild.name}")
                return

            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await utils.create_flag_embed(guild_id, map_key)
            embed.timestamp = discord.utils.utcnow()

            view = FlagManageView(guild, map_key, getattr(self, 'bot', None))
            await msg.edit(embed=embed, view=view)
            log.info(f"✅ Refreshed flag message for {map_key} in {guild.name}")

        except discord.NotFound:
            log.warning(f"⚠️ Message not found for {map_key} in {guild.name}")
        except discord.Forbidden:
            log.warning(f"🚫 Missing permission to edit message for {map_key} in {guild.name}")
        except Exception as e:
            log.error(f"❌ Failed to update flag message for {map_key} in {guild.name}: {e}", exc_info=True)
