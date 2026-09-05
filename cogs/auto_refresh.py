from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from cogs import utils
from cogs.ui.flag_views import FlagManageView

log = logging.getLogger("dayz-manager")


class AutoRefresh(commands.Cog):
    """Restores every persistent flag message after startup/reconnect."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def restore(
        self,
        guild: discord.Guild,
        map_key: str,
        server: str,
        channel_id: str,
        message_id: str,
    ) -> None:
        channel = guild.get_channel(int(channel_id))

        if not isinstance(channel, discord.TextChannel):
            log.warning(
                "Flag channel missing | guild=%s map=%s server=%s",
                guild.id, map_key, server
            )
            return

        try:
            message = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            log.warning(
                "Flag message missing | guild=%s map=%s server=%s",
                guild.id, map_key, server
            )
            return
        except discord.Forbidden:
            log.warning(
                "No permission to read flag message | guild=%s",
                guild.id
            )
            return
        except discord.HTTPException:
            log.exception("Discord error reading flag message.")
            return

        view = await FlagManageView.create(
            guild,
            map_key,
            server,
            self.bot,
        )

        try:
            if getattr(message.flags, "components_v2", False):
                await message.edit(view=view)
                try:
                    self.bot.add_view(view, message_id=message.id)
                except ValueError:
                    pass
            else:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                message = await channel.send(view=view)
                await utils.save_flag_message(
                    str(guild.id), map_key, server, str(channel.id), str(message.id)
                )
                try:
                    self.bot.add_view(view, message_id=message.id)
                except ValueError:
                    pass
        except discord.HTTPException:
            log.exception(
                "Failed to refresh flag message | guild=%s map=%s server=%s",
                guild.id, map_key, server
            )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if getattr(self.bot, "_auto_refresh_done", False):
            return

        self.bot._auto_refresh_done = True
        await asyncio.sleep(2)

        log.info("Restoring persistent flag views...")

        for guild in self.bot.guilds:
            try:
                sessions = await utils.get_flag_sessions(str(guild.id))
                for row in sessions:
                    await self.restore(
                        guild,
                        row["map"],
                        row["server"],
                        row["channel_id"],
                        row["message_id"],
                    )
                    await asyncio.sleep(0.25)
            except Exception:
                log.exception(
                    "Failed restoring flag sessions for guild %s.",
                    guild.id
                )

        log.info("Persistent flag restoration complete.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
