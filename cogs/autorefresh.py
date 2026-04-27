import asyncio
import discord
from discord.ext import commands
from cogs import utils
from cogs.ui_views import FlagManageView


class AutoRefresh(commands.Cog):
    """Automatically refreshes all active flag embeds on startup (no new channels created)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_flag_message(self, guild: discord.Guild, map_key: str):
        """Refresh existing flag message for a given map, restoring persistent view."""
        guild_id = str(guild.id)

        if map_key not in utils.MAP_DATA:
            return

        async with utils.safe_acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id,
                map_key,
            )

        if not row:
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            return

        try:
            embed = await utils.create_flag_embed(guild_id, map_key)
            embed.timestamp = discord.utils.utcnow()

            msg = await channel.fetch_message(int(row["message_id"]))
            view = FlagManageView(guild, map_key, self.bot)

            await msg.edit(embed=embed, view=view)

        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()

        if getattr(self.bot, "_refresh_done", False):
            return
        self.bot._refresh_done = True

        await asyncio.sleep(5)

        for guild in self.bot.guilds:
            guild_id = str(guild.id)

            try:
                async with utils.safe_acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT map FROM flag_messages WHERE guild_id=$1",
                        guild_id,
                    )

                if not rows:
                    continue

                map_keys = [r["map"] for r in rows]

                for map_key in map_keys:
                    await self.ensure_flag_message(guild, map_key)
                    await asyncio.sleep(1)

            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
