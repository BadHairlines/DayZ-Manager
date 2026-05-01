import asyncio
import logging
import discord
from discord.ext import commands

from cogs import utils
from cogs.ui_views import FlagManageView

log = logging.getLogger("dayz-manager")


class AutoRefresh(commands.Cog):
    """Automatically restores persistent flag embeds on startup."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- REFRESH SINGLE MAP ----------------

    async def ensure_flag_message(self, guild: discord.Guild, map_key: str):
        guild_id = str(guild.id)

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
                    guild_id,
                    map_key,
                )

            if not row:
                return

            channel = guild.get_channel(int(row["channel_id"]))
            if not channel:
                log.warning(f"[AutoRefresh] Missing channel for {guild.name} ({map_key})")
                return

            embed = await utils.create_flag_embed(guild_id, map_key)
            embed.timestamp = discord.utils.utcnow()

            msg = await channel.fetch_message(int(row["message_id"]))
            view = FlagManageView(guild, map_key, self.bot)

            await msg.edit(embed=embed, view=view)

        except discord.NotFound:
            log.warning(f"[AutoRefresh] Message not found for {guild.name} ({map_key})")

        except discord.Forbidden:
            log.warning(f"[AutoRefresh] No permission for {guild.name} ({map_key})")

        except Exception as e:
            log.error(f"[AutoRefresh ERROR] {guild.name} ({map_key}): {e}")

    # ---------------- ON READY ----------------

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()

        # prevent double-run on reconnects
        if getattr(self.bot, "_refresh_done", False):
            return
        self.bot._refresh_done = True

        await asyncio.sleep(5)

        log.info("[AutoRefresh] Starting flag embed restoration...")

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

                # remove duplicates + stabilize order
                map_keys = sorted({r["map"] for r in rows})

                for map_key in map_keys:
                    await self.ensure_flag_message(guild, map_key)
                    await asyncio.sleep(0.8)  # rate-limit safety

            except Exception as e:
                log.error(f"[AutoRefresh Guild Error] {guild.name}: {e}")

        log.info("[AutoRefresh] Completed flag embed restoration.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
