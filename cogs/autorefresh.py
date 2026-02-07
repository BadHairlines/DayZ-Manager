# cogs/auto_refresh.py
import asyncio
import logging
import discord
from discord.ext import commands
from cogs import utils
from cogs.ui_views import FlagManageView

log = logging.getLogger("dayz-manager")


class AutoRefresh(commands.Cog):
    """Automatically refreshes all active flag embeds on startup (no new channels created)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_flag_message(self, guild: discord.Guild, map_key: str):
        """Refresh existing flag message for a given map, restoring persistent view."""
        guild_id = str(guild.id)

        if map_key not in utils.MAP_DATA:
            log.warning(f"⚠️ Skipping unknown map '{map_key}' for {guild.name}")
            return

        async with utils.safe_acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )

        if not row:
            log.info(f"⏭️ {utils.MAP_DATA[map_key]['name']} not set up yet in {guild.name}.")
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            log.warning(f"⚠️ Channel missing for {guild.name} ({map_key}); skipping refresh.")
            log.info(f"   💡 Run `/setup {utils.MAP_DATA[map_key]['name']}` to rebuild it.")
            return

        try:
            embed = await utils.create_flag_embed(guild_id, map_key)
            embed.timestamp = discord.utils.utcnow()
            msg = await channel.fetch_message(int(row["message_id"]))

            view = FlagManageView(guild, map_key, self.bot)
            await msg.edit(embed=embed, view=view)

            log.info(f"🔄 Refreshed flag display for {guild.name} → {utils.MAP_DATA[map_key]['name']}")
        except discord.NotFound:
            log.warning(f"⚠️ Flag message missing for {guild.name} ({map_key}). Skipping.")
            log.info(f"   💡 Use `/setup {utils.MAP_DATA[map_key]['name']}` to recreate it.")
        except discord.Forbidden:
            log.error(f"🚫 Missing permission to edit flag message in {guild.name} ({map_key})")
        except Exception as e:
            log.error(f"❌ Unexpected error updating message for {guild.name} ({map_key}): {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-refresh flag messages on bot startup (no channel creation)."""
        await self.bot.wait_until_ready()

        if getattr(self.bot, "_refresh_done", False):
            return
        self.bot._refresh_done = True

        log.info("🚀 DayZ Manager starting flag auto-refresh...")
        await asyncio.sleep(5)

        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            try:
                async with utils.safe_acquire() as conn:
                    rows = await conn.fetch("SELECT map FROM flag_messages WHERE guild_id=$1", guild_id)

                if not rows:
                    log.info(f"⚠️ No maps set up for {guild.name}. Skipping.")
                    continue

                map_keys = [r["map"] for r in rows]
                log.info(f"🔍 Found maps in DB for {guild.name}: {map_keys}")

                # Refresh sequentially (safer for Discord rate limits)
                for map_key in map_keys:
                    await self.ensure_flag_message(guild, map_key)
                    await asyncio.sleep(1)

            except Exception as e:
                log.error(f"⚠️ Error during refresh for {guild.name}: {e}", exc_info=True)

        log.info("✅ Auto-refresh complete (no channels or messages created).")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
