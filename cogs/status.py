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
    """Admin system health + flag statistics."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------------
    # UPTIME
    # -------------------------
    def format_uptime(self) -> str:
        start = getattr(self.bot, "start_time", None)
        if not start:
            return "Unknown"

        delta: timedelta = discord.utils.utcnow() - start

        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

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
    async def get_guild_stats(self, guild: discord.Guild):
        try:
            async with utils.safe_acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM flag_messages WHERE guild_id=$1",
                    str(guild.id),
                )

            return "Connected", count or 0

        except Exception as e:
            log.warning(f"DB status check failed: {e}")
            return "Unavailable", 0

    # -------------------------
    # FLAG STATS
    # -------------------------
    async def get_flag_stats(self, guild: discord.Guild):
        async with utils.safe_acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    map,
                    COUNT(*) FILTER (WHERE role_id IS NOT NULL) AS assigned,
                    COUNT(*) AS total
                FROM flags
                WHERE guild_id = $1
                GROUP BY map
                ORDER BY map
            """, str(guild.id))

        return rows

    # -------------------------
    # /status
    # -------------------------
    @app_commands.command(
        name="status",
        description="Show bot uptime, latency, and database health.",
    )
    @admin_only()
    async def status(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        db_status, map_count = await self.get_guild_stats(guild)
        latency = round(self.bot.latency * 1000)
        uptime = self.format_uptime()

        embed = self.make_embed(
            title="🧭 DayZ Manager Status",
            desc=(
                f"**Uptime:** {uptime}\n"
                f"**Latency:** {latency}ms\n"
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
    # /flagstats
    # -------------------------
    @app_commands.command(
        name="flagstats",
        description="Show flag assignment statistics per map.",
    )
    @admin_only()
    async def flagstats(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        try:
            rows = await self.get_flag_stats(guild)
        except Exception as e:
            log.warning(f"Flag stats failed: {e}")
            return await interaction.followup.send(
                "❌ Unable to load stats.",
                ephemeral=True,
            )

        if not rows:
            return await interaction.followup.send(
                "ℹ️ No flag data found. Run `/setup` first.",
                ephemeral=True,
            )

        total_assigned = sum(r["assigned"] for r in rows)
        total_flags = sum(r["total"] for r in rows)
        total_unassigned = total_flags - total_assigned

        embed = self.make_embed(
            title="🏴 Flag Overview",
            desc=(
                f"**Total Flags:** {total_flags}\n"
                f"**Assigned:** {total_assigned}\n"
                f"**Unassigned:** {total_unassigned}"
            ),
            color=0x2ECC71,
            author_icon="🗺️",
            author_name="Flag Stats",
        )

        for row in rows:
            map_info = utils.MAP_DATA.get(row["map"], {"name": row["map"].title()})

            assigned = row["assigned"]
            total = row["total"]
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
