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

    # -------------------------
    # UPTIME
    # -------------------------
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

    # -------------------------
    # GUILD STATS
    # -------------------------
    async def _get_guild_stats(self, guild: discord.Guild) -> tuple[str, str]:
        """DB health + number of maps configured."""
        try:
            await utils.ensure_connection()

            async with utils.safe_acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM flag_messages WHERE guild_id=$1",
                    str(guild.id),
                )

            return "✅ Connected", str(count or 0)

        except Exception as exc:
            log.warning(f"Status DB check failed for {guild.name}: {exc}")
            return "❌ Unavailable", "0"

    # -------------------------
    # FLAG STATS (CLEAN VERSION)
    # -------------------------
    async def _get_flag_stats(self, guild: discord.Guild) -> list[tuple[str, int, int]]:
        """Returns (map, assigned_flags, total_flags)."""
        await utils.ensure_connection()

        async with utils.safe_acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    map,
                    COUNT(*) FILTER (WHERE role_id IS NOT NULL) AS assigned_count,
                    COUNT(*) AS total_count
                FROM flags
                WHERE guild_id = $1
                GROUP BY map
                ORDER BY map
                """,
                str(guild.id),
            )

        return [
            (row["map"], int(row["assigned_count"]), int(row["total_count"]))
            for row in rows
        ]

    # -------------------------
    # STATUS COMMAND
    # -------------------------
    @app_commands.command(
        name="status",
        description="Show bot uptime, latency, and database health.",
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
                f"**Database:** {db_status}\n"
                f"**Maps Configured:** {map_count}\n"
                f"**Servers Connected:** {len(self.bot.guilds)}"
            ),
            color=0x3498DB,
            author_icon="📊",
            author_name="System Status",
        )

        embed.set_footer(text=f"DayZ Manager • {guild.name}")

        await interaction.followup.send(embed=embed, ephemeral=True)

    # -------------------------
    # FLAG STATS COMMAND
    # -------------------------
    @app_commands.command(
        name="flagstats",
        description="Show flag assignment statistics for each map.",
    )
    @admin_only()
    async def flagstats(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        guild = interaction.guild
        if not guild:
            return await interaction.followup.send(
                "❌ This command can only be used inside a server.",
                ephemeral=True,
            )

        try:
            stats = await self._get_flag_stats(guild)
        except Exception as exc:
            log.warning(f"Flag stats lookup failed for {guild.name}: {exc}")
            return await interaction.followup.send(
                "❌ Unable to load flag stats right now.",
                ephemeral=True,
            )

        if not stats:
            return await interaction.followup.send(
                "ℹ️ No flag data found. Run `/setup` first.",
                ephemeral=True,
            )

        total_assigned = sum(a for _, a, _ in stats)
        total_flags = sum(t for _, _, t in stats)
        total_unassigned = total_flags - total_assigned

        embed = self.make_embed(
            title="🏴 Flag Assignment Overview",
            desc=(
                f"**Total Flags:** {total_flags}\n"
                f"**Assigned:** {total_assigned}\n"
                f"**Unassigned:** {total_unassigned}"
            ),
            color=0x2ECC71,
            author_icon="🗺️",
            author_name="Flag Stats",
        )

        for map_key, assigned, total in stats:
            map_info = utils.MAP_DATA.get(map_key, {"name": map_key.title()})
            unassigned = total - assigned

            embed.add_field(
                name=map_info["name"],
                value=(
                    f"Assigned: **{assigned}**\n"
                    f"Unassigned: **{unassigned}**\n"
                    f"Total: **{total}**"
                ),
                inline=True,
            )

        embed.set_footer(text=f"DayZ Manager • {guild.name}")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))
