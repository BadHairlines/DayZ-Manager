import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from cogs import utils
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only

log = logging.getLogger("dayz-manager")


class Status(commands.Cog, BaseCog):
    """Provides a quick health/status snapshot for administrators."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _format_uptime(self) -> str:
        start_time = getattr(self.bot, "start_time", None)
        if not start_time:
            return "Unknown"
        delta: timedelta = discord.utils.utcnow() - start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

    async def _get_guild_stats(self, guild: discord.Guild) -> tuple[str, str]:
        """Return (db_status, map_count_text) for the guild."""
        try:
            await utils.ensure_connection()
            async with utils.safe_acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM flag_messages WHERE guild_id=$1",
                    str(guild.id),
                )
            return "✅ Connected", f"{count}"
        except Exception as exc:
            log.warning(f"Status DB check failed for {guild.name}: {exc}")
            return "❌ Unavailable", "N/A"

    @app_commands.command(
        name="status",
        description="Show bot uptime, latency, and database health for this server.",
    )
    @admin_only()
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        guild = interaction.guild
        if not guild:
            return await interaction.followup.send(
                "❌ This command can only be used inside a server.",
                ephemeral=True,
            )

        db_status, map_count = await self._get_guild_stats(guild)
        latency_ms = round(self.bot.latency * 1000)
        uptime = self._format_uptime()

        embed = self.make_embed(
            title="🧭 DayZ Manager Status",
            desc=(
                f"**Uptime:** {uptime}\n"
                f"**Latency:** {latency_ms} ms\n"
                f"**DB Status:** {db_status}\n"
                f"**Maps Set Up (this server):** {map_count}\n"
                f"**Servers Connected:** {len(self.bot.guilds)}"
            ),
            color=0x3498DB,
            author_icon="📊",
            author_name="Status",
        )
        embed.set_footer(text=f"DayZ Manager • {guild.name}")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))
