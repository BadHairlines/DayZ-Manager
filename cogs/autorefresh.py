import asyncio
import logging
import discord
from discord.ext import commands

from cogs import utils
from cogs.ui_views import FlagManageView

log = logging.getLogger("dayz-manager")


class AutoRefresh(commands.Cog):
    """Restores persistent flag embeds after bot restart."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------
    # SINGLE EMBED RESTORE
    # -----------------------------
    async def restore_flag_message(self, guild: discord.Guild, map_key: str):
        if map_key not in utils.MAP_DATA:
            return

        try:
            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT channel_id, message_id
                    FROM flag_messages
                    WHERE guild_id=$1 AND map=$2
                    """,
                    str(guild.id),
                    map_key,
                )

            if not row:
                return

            channel = guild.get_channel(int(row["channel_id"]))
            if not channel:
                log.warning(f"[AutoRefresh] Missing channel: {guild.name} ({map_key})")
                return

            try:
                msg = await channel.fetch_message(int(row["message_id"]))
            except discord.NotFound:
                log.warning(f"[AutoRefresh] Missing message: {guild.name} ({map_key})")
                return
            except discord.Forbidden:
                log.warning(f"[AutoRefresh] No permission to fetch message: {guild.name} ({map_key})")
                return

            embed = await utils.create_flag_embed(str(guild.id), map_key)

            # IMPORTANT FIX:
            # Always reuse same view instance per (guild, map)
            view = FlagManageView(guild, map_key, self.bot)

            await msg.edit(embed=embed, view=view)

        except Exception as e:
            log.error(f"[AutoRefresh ERROR] {guild.name} ({map_key}): {type(e).__name__}: {e}")

    # -----------------------------
    # STARTUP RESTORE
    # -----------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()

        # prevent duplicate execution on reconnect
        if getattr(self.bot, "_auto_refresh_done", False):
            return
        self.bot._auto_refresh_done = True

        log.info("[AutoRefresh] Restoring persistent flag embeds...")

        # small delay lets cache + guilds stabilize
        await asyncio.sleep(3)

        for guild in self.bot.guilds:
            try:
                async with utils.safe_acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT DISTINCT map
                        FROM flag_messages
                        WHERE guild_id=$1
                        """,
                        str(guild.id),
                    )

                if not rows:
                    continue

                map_keys = [r["map"] for r in rows]

                # restore sequentially (safe for rate limits)
                for map_key in map_keys:
                    await self.restore_flag_message(guild, map_key)
                    await asyncio.sleep(0.6)

            except Exception as e:
                log.error(f"[AutoRefresh Guild Error] {guild.name}: {type(e).__name__}: {e}")

        log.info("[AutoRefresh] Completed restoration.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
