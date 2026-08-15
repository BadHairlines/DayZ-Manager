import asyncio
import logging

import discord
from discord.ext import commands

from cogs import utils
from cogs.ui_views import FlagManageView


log = logging.getLogger("dayz-manager")


class AutoRefresh(commands.Cog):
    """
    Restores persistent flag embeds after bot restart.
    Supports multiple servers on the same map.
    """

    def __init__(
        self,
        bot: commands.Bot
    ):
        self.bot = bot

    async def restore_flag_message(
        self,
        guild: discord.Guild,
        map_key: str,
        server: str
    ):

        if map_key not in utils.MAP_DATA:
            return

        try:

            async with utils.safe_acquire() as conn:

                row = await conn.fetchrow(
                    """
                    SELECT channel_id, message_id
                    FROM flag_messages
                    WHERE guild_id=$1
                      AND map=$2
                      AND server=$3
                    """,
                    str(guild.id),
                    map_key,
                    server
                )

            if not row:
                return

            channel = guild.get_channel(
                int(row["channel_id"])
            )

            if not channel:

                log.warning(
                    f"[AutoRefresh] Missing channel: "
                    f"{guild.name} "
                    f"({map_key} / {server})"
                )

                return

            try:

                msg = await channel.fetch_message(
                    int(row["message_id"])
                )

            except discord.NotFound:

                log.warning(
                    f"[AutoRefresh] Missing message: "
                    f"{guild.name} "
                    f"({map_key} / {server})"
                )

                return

            except discord.Forbidden:

                log.warning(
                    f"[AutoRefresh] No permission: "
                    f"{guild.name} "
                    f"({map_key} / {server})"
                )

                return

            embed = await utils.create_flag_embed(
                str(guild.id),
                map_key,
                server
            )

            view = FlagManageView(
                guild,
                map_key,
                server,
                self.bot
            )

            # Register persistent view
            self.bot.add_view(
                view,
                message_id=msg.id
            )

            await msg.edit(
                embed=embed,
                view=view
            )

        except Exception as e:

            log.error(
                f"[AutoRefresh ERROR] "
                f"{guild.name} "
                f"({map_key} / {server}): "
                f"{type(e).__name__}: {e}"
            )

    # -----------------------------
    # STARTUP
    # -----------------------------
    @commands.Cog.listener()
    async def on_ready(self):

        await self.bot.wait_until_ready()

        if getattr(
            self.bot,
            "_auto_refresh_done",
            False
        ):
            return

        self.bot._auto_refresh_done = True

        log.info(
            "[AutoRefresh] Restoring persistent flag embeds..."
        )

        await asyncio.sleep(3)

        for guild in self.bot.guilds:

            try:

                async with utils.safe_acquire() as conn:

                    rows = await conn.fetch(
                        """
                        SELECT map, server
                        FROM flag_messages
                        WHERE guild_id=$1
                        ORDER BY map, server
                        """,
                        str(guild.id)
                    )

                if not rows:
                    continue

                for row in rows:

                    await self.restore_flag_message(
                        guild,
                        row["map"],
                        row["server"]
                    )

                    await asyncio.sleep(
                        0.6
                    )

            except Exception as e:

                log.error(
                    f"[AutoRefresh Guild Error] "
                    f"{guild.name}: "
                    f"{type(e).__name__}: {e}"
                )

        log.info(
            "[AutoRefresh] Completed restoration."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        AutoRefresh(bot)
    )
