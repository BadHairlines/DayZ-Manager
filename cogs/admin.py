from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs import utils
from cogs.decorators import MAP_CHOICES, admin_only, normalize_map
from cogs.ui.flag_views import FlagManageView

log = logging.getLogger("dayz-manager")


class DeleteSetupConfirmView(discord.ui.View):
    """One-use confirmation view for deleting a guild-scoped flag setup."""

    def __init__(
        self,
        *,
        author_id: int,
        guild: discord.Guild,
        map_key: str,
        server: str,
        stored_message,
        delete_channel: bool,
    ) -> None:
        super().__init__(timeout=60)
        self.author_id = author_id
        self.guild = guild
        self.map_key = map_key
        self.server = server
        self.stored_message = stored_message
        self.delete_channel = delete_channel
        self.completed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the administrator who started this deletion can confirm it.",
                ephemeral=True,
            )
            return False
        return True

    async def _disable(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except (discord.NotFound, discord.HTTPException):
            pass

    @discord.ui.button(
        label="Delete Setup",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.completed:
            return await interaction.response.send_message(
                "ℹ️ This deletion has already been handled.", ephemeral=True
            )

        self.completed = True
        await interaction.response.defer(ephemeral=True, thinking=True)

        channel_deleted = False
        category_deleted = False
        channel_note = "Channel cleanup was not requested."

        try:
            counts = await utils.delete_flag_session(
                str(self.guild.id),
                self.map_key,
                self.server,
            )

            if self.delete_channel and self.stored_message:
                channel = self.guild.get_channel(int(self.stored_message["channel_id"]))
                if isinstance(channel, discord.TextChannel):
                    category = channel.category
                    category_was_setup_only = (
                        category is not None
                        and len(category.channels) == 1
                        and category.channels[0].id == channel.id
                    )
                    try:
                        await channel.delete(
                            reason=(
                                f"DayZ Manager setup deleted by "
                                f"{interaction.user} ({interaction.user.id})"
                            )
                        )
                        channel_deleted = True
                        channel_note = "The flag channel was deleted."
                    except discord.Forbidden:
                        channel_note = "Database deleted, but I do not have permission to delete the flag channel."
                    except discord.HTTPException:
                        channel_note = "Database deleted, but Discord returned an error while deleting the flag channel."

                    if channel_deleted and category_was_setup_only and category is not None:
                        try:
                            await category.delete(
                                reason="DayZ Manager removed an empty flag setup category"
                            )
                            category_deleted = True
                        except (discord.Forbidden, discord.HTTPException):
                            pass
                else:
                    channel_note = "The stored flag channel was already missing."

            await self._disable(interaction)

            map_name = utils.MAP_DATA.get(self.map_key, {}).get(
                "name", self.map_key.title()
            )
            embed = discord.Embed(
                title="🗑️ Setup Deleted",
                description=(
                    f"The flag setup for **{map_name} — {self.server}** has been permanently removed."
                ),
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Flags removed", value=str(counts["flags"]))
            embed.add_field(name="Message record", value="Removed" if counts["messages"] else "Not found")
            embed.add_field(name="History entries removed", value=str(counts["audit"]))
            embed.add_field(name="Discord cleanup", value=channel_note, inline=False)
            if category_deleted:
                embed.add_field(name="Category", value="Empty setup category deleted", inline=False)
            embed.set_footer(text="DayZ Manager • This action cannot be undone")

            await interaction.followup.send(embed=embed, ephemeral=True)
            self.stop()

        except Exception:
            self.completed = False
            log.exception(
                "Failed deleting flag setup | guild=%s map=%s server=%s",
                self.guild.id,
                self.map_key,
                self.server,
            )
            await interaction.followup.send(
                "❌ The setup could not be deleted. Check the bot logs for the full error.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="✖️",
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.completed = True
        await interaction.response.edit_message(
            content="✅ Setup deletion cancelled.",
            embed=None,
            view=None,
        )
        self.stop()


class FlagAdmin(commands.Cog):
    """Administrative visibility, cleanup, and recovery tools for flag sessions."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def setup_server_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []

        try:
            rows = await utils.get_flag_sessions(str(interaction.guild.id))
        except Exception:
            log.exception("Failed loading setup autocomplete for guild %s", interaction.guild.id)
            return []

        selected = getattr(interaction.namespace, "selected_map", None)
        selected_map = normalize_map(selected) if selected else ""
        current_cf = current.casefold()

        servers: list[str] = []
        for row in rows:
            if selected_map and utils.normalize_map(row["map"]) != selected_map:
                continue
            server = str(row["server"])
            if current_cf not in server.casefold():
                continue
            if server not in servers:
                servers.append(server)

        return [app_commands.Choice(name=name, value=name) for name in servers[:25]]

    @app_commands.command(
        name="setups",
        description="List all DayZ Manager flag setups in this Discord server.",
    )
    @admin_only()
    async def setups(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True, thinking=True)
        rows = await utils.get_flag_sessions(str(guild.id))

        if not rows:
            return await interaction.followup.send(
                "ℹ️ This Discord server does not currently have any saved flag setups.",
                ephemeral=True,
            )

        lines: list[str] = []
        for row in rows:
            map_key = utils.normalize_map(row["map"])
            map_name = utils.MAP_DATA.get(map_key, {}).get("name", map_key.title())
            channel = guild.get_channel(int(row["channel_id"]))
            channel_text = channel.mention if isinstance(channel, discord.TextChannel) else "⚠️ Missing channel"
            lines.append(f"• **{map_name} — {row['server']}**\n  {channel_text}")

        embed = discord.Embed(
            title="🗂️ Flag Setups",
            description="\n\n".join(lines),
            color=0x3498DB,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"{len(rows)} setup(s) • Use /deletesetup to remove one")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="deletesetup",
        description="Permanently delete one flag setup from this Discord server.",
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Map used by the setup.",
        server="Server setup to delete.",
        delete_channel="Also delete the setup's Discord channel (default: yes).",
    )
    @app_commands.autocomplete(server=setup_server_autocomplete)
    async def deletesetup(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
        delete_channel: bool = True,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        map_key = normalize_map(selected_map)
        server_key = utils.normalize_server(server)

        if not server_key:
            return await interaction.response.send_message(
                "❌ Select or enter a valid server setup.", ephemeral=True
            )

        exists = await utils.flag_session_exists(str(guild.id), map_key, server_key)
        if not exists:
            return await interaction.response.send_message(
                "⚠️ I couldn't find that setup in **this Discord server**. Use `/setups` to see the setups you can manage.",
                ephemeral=True,
            )

        stored = await utils.get_flag_message(str(guild.id), map_key, server_key)
        map_name = utils.MAP_DATA.get(map_key, {}).get("name", map_key.title())

        cleanup_text = "Yes — delete its stored flag channel too." if delete_channel else "No — leave the Discord channel in place."
        embed = discord.Embed(
            title="⚠️ Delete Flag Setup?",
            description=(
                f"You are about to permanently delete:\n\n"
                f"**Map:** `{map_name}`\n"
                f"**Server:** `{server_key}`\n"
                f"**Delete channel:** {cleanup_text}\n\n"
                "This removes the setup's flags, saved message record, and claim/release history. "
                "**This cannot be undone.**"
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Only you can confirm this deletion • Confirmation expires in 60 seconds")

        view = DeleteSetupConfirmView(
            author_id=interaction.user.id,
            guild=guild,
            map_key=map_key,
            server=server_key,
            stored_message=stored,
            delete_channel=delete_channel,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
