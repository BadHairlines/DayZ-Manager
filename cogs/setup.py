from __future__ import annotations

import logging

import discord
from discord import Embed, Interaction, app_commands
from discord.ext import commands

from cogs import utils
from cogs.helpers.decorators import MAP_CHOICES, admin_only, normalize_map
from cogs.ui.flag_views import FlagManageView

log = logging.getLogger("dayz-manager")


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_or_create_category(self, guild, name: str, reason: str):
        category = discord.utils.get(guild.categories, name=name)
        if category:
            return category
        return await guild.create_category(name=name, reason=reason)

    async def get_or_create_text_channel(
        self,
        guild,
        name: str,
        category,
        reason: str,
        seed_message: str | None = None,
    ):
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel:
            if category and channel.category_id != category.id:
                try:
                    await channel.edit(category=category, reason=reason)
                except discord.HTTPException:
                    pass
            return channel

        channel = await guild.create_text_channel(
            name=name,
            category=category,
            reason=reason,
        )

        if seed_message:
            await channel.send(seed_message)

        return channel

    @app_commands.command(
        name="setup",
        description="Set up the flag system for a server.",
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Map for this flag system.",
        server="Server name/identifier, e.g. Livonia #1.",
    )
    async def setup(
        self,
        interaction: Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "❌ Server only.", ephemeral=True
            )

        server = utils.normalize_server(server)
        if not server:
            return await interaction.response.send_message(
                "❌ You must provide a server name.", ephemeral=True
            )

        if len(server) > 50:
            return await interaction.response.send_message(
                "❌ Server name must be 50 characters or less.", ephemeral=True
            )

        map_key = normalize_map(selected_map)
        map_info = utils.MAP_DATA.get(map_key)

        if not map_info:
            return await interaction.response.send_message(
                "❌ Invalid map.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await utils.ensure_connection()
            await utils.initialize_flags(str(guild.id), map_key, server)

            category = await self.get_or_create_category(
                guild,
                f"🌍 {map_info['name']} — {server}",
                "Flag System Setup",
            )

            channel = await self.get_or_create_text_channel(
                guild,
                utils.channel_name_for(map_key, server),
                category,
                "Flag System Setup",
                (
                    f"📜 **{map_info['name']} Flag System Initialized**\n"
                    f"🖥️ Server: **{server}**"
                ),
            )

            embed = await utils.create_flag_embed(
                str(guild.id), map_key, server, guild
            )
            view = FlagManageView(guild, map_key, server, self.bot)

            stored = await utils.get_flag_message(
                str(guild.id), map_key, server
            )

            message = None

            if stored:
                old_channel = guild.get_channel(int(stored["channel_id"]))
                if isinstance(old_channel, discord.TextChannel):
                    try:
                        message = await old_channel.fetch_message(
                            int(stored["message_id"])
                        )
                        await message.edit(embed=embed, view=view)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        message = None

            if message is None:
                message = await channel.send(embed=embed, view=view)

            await utils.save_flag_message(
                str(guild.id),
                map_key,
                server,
                str(channel.id),
                str(message.id),
            )

            self.bot.add_view(view, message_id=message.id)

            await interaction.edit_original_response(
                embed=Embed(
                    title="✅ SETUP COMPLETE",
                    description=(
                        f"**Map:** `{map_info['name']}`\n"
                        f"**Server:** `{server}`\n"
                        f"**Channel:** {channel.mention}\n\n"
                        "The flag system is ready and will persist through bot restarts."
                    ),
                    color=discord.Color.green(),
                ),
            )

        except Exception as exc:
            log.exception("Flag setup failed for guild %s.", guild.id)
            await interaction.edit_original_response(
                content=(
                    "❌ **Setup failed.**\n"
                    "Check the bot logs for the full error."
                ),
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
