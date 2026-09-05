from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs import utils
from cogs.decorators import MAP_CHOICES, admin_only, normalize_map
from cogs.ui.flag_views import FlagManageView

log = logging.getLogger("dayz-manager")


class FlagAdmin(commands.Cog):
    """Administrative visibility and recovery tools for flag sessions."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="flagstatus",
        description="Show the health and ownership summary for a flag session.",
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    async def flagstatus(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        map_key = normalize_map(selected_map)
        server_key = utils.normalize_server(server)
        await interaction.response.defer(ephemeral=True, thinking=True)

        flags = await utils.get_all_flags(str(guild.id), map_key, server_key)
        stored = await utils.get_flag_message(str(guild.id), map_key, server_key)

        if not flags:
            return await interaction.followup.send(
                "⚠️ No flag session exists for that map/server. Run `/setup` first.",
                ephemeral=True,
            )

        claimed = [row for row in flags if row["status"] == "❌" and row["role_id"]]
        available = len(flags) - len(claimed)
        missing_roles = sum(
            1 for row in claimed
            if guild.get_role(int(row["role_id"])) is None
        )

        message_state = "Not stored"
        channel_text = "Not stored"
        if stored:
            channel = guild.get_channel(int(stored["channel_id"]))
            channel_text = channel.mention if isinstance(channel, discord.TextChannel) else "Missing channel"
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.fetch_message(int(stored["message_id"]))
                    message_state = "✅ Reachable"
                except discord.NotFound:
                    message_state = "❌ Missing message"
                except discord.Forbidden:
                    message_state = "🚫 No permission"
                except discord.HTTPException:
                    message_state = "⚠️ Discord error"

        embed = discord.Embed(
            title="🏴 Flag Session Status",
            color=0x3498DB,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Map", value=utils.MAP_DATA.get(map_key, {}).get("name", map_key.title()))
        embed.add_field(name="Server", value=server_key)
        embed.add_field(name="Flags", value=f"🟩 {available} available\n🟥 {len(claimed)} claimed")
        embed.add_field(name="Channel", value=channel_text, inline=False)
        embed.add_field(name="Public message", value=message_state)
        embed.add_field(name="Missing roles", value=str(missing_roles))
        embed.set_footer(text="DayZ Manager • Flag Admin")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="flagrefresh",
        description="Force-refresh a stored public flag message and persistent buttons.",
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    async def flagrefresh(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        map_key = normalize_map(selected_map)
        server_key = utils.normalize_server(server)
        await interaction.response.defer(ephemeral=True, thinking=True)

        stored = await utils.get_flag_message(str(guild.id), map_key, server_key)
        if not stored:
            return await interaction.followup.send(
                "⚠️ No stored public flag message was found for that session.", ephemeral=True
            )

        channel = guild.get_channel(int(stored["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return await interaction.followup.send("❌ The stored channel no longer exists.", ephemeral=True)

        try:
            message = await channel.fetch_message(int(stored["message_id"]))
        except discord.NotFound:
            return await interaction.followup.send(
                "❌ The stored flag message no longer exists. Run `/setup` to recreate it.", ephemeral=True
            )

        view = FlagManageView(guild, map_key, server_key, self.bot)
        embed = await utils.create_flag_embed(str(guild.id), map_key, server_key, guild)
        try:
            self.bot.add_view(view, message_id=message.id)
        except ValueError:
            pass
        await message.edit(embed=embed, view=view)

        await interaction.followup.send(
            f"✅ Refreshed the flag message in {channel.mention}.", ephemeral=True
        )

    @app_commands.command(
        name="flaghistory",
        description="Show recent claim/release activity for a flag session.",
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    async def flaghistory(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
        limit: app_commands.Range[int, 1, 20] = 10,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        map_key = normalize_map(selected_map)
        server_key = utils.normalize_server(server)
        await interaction.response.defer(ephemeral=True, thinking=True)

        rows = await utils.get_flag_history(str(guild.id), map_key, server_key, limit)
        if not rows:
            return await interaction.followup.send(
                "ℹ️ No audited flag activity has been recorded for this session yet.", ephemeral=True
            )

        lines: list[str] = []
        for row in rows:
            icon = "🏴" if row["action"] == "claim" else "🏳️"
            actor = f"<@{row['actor_id']}>" if row["actor_id"] else "Unknown"
            role = f"<@&{row['role_id']}>" if row["role_id"] else "No role"
            timestamp = int(row["created_at"].timestamp())
            lines.append(
                f"{icon} **{row['flag']}** • {row['action'].title()} • {role}\n"
                f"└ {actor} • <t:{timestamp}:R> • `{row['source']}`"
            )

        embed = discord.Embed(
            title="📜 Flag Activity History",
            description="\n\n".join(lines),
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"{utils.MAP_DATA.get(map_key, {}).get('name', map_key.title())} • {server_key}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="botstatus",
        description="Show DayZ Manager runtime and database status.",
    )
    @admin_only()
    async def botstatus(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        db_ok = True
        try:
            pool = await utils.ensure_connection()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception:
            db_ok = False
            log.exception("Database health check failed.")

        started_at = getattr(self.bot, "started_at", discord.utils.utcnow())
        uptime = discord.utils.utcnow() - started_at
        total_seconds = max(0, int(uptime.total_seconds()))
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)

        embed = discord.Embed(
            title="🤖 DayZ Manager Status",
            color=0x2ECC71 if db_ok else 0xE74C3C,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Discord", value="✅ Connected" if self.bot.is_ready() else "⚠️ Connecting")
        embed.add_field(name="Database", value="✅ Healthy" if db_ok else "❌ Unavailable")
        embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.0f} ms")
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)))
        embed.add_field(name="Uptime", value=f"{days}d {hours}h {minutes}m")
        embed.add_field(name="Commands", value=str(len(self.bot.tree.get_commands())))
        embed.set_footer(text="DayZ Manager • Runtime Health")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FlagAdmin(bot))
