from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs import utils
from cogs.decorators import MAP_CHOICES, admin_only, normalize_map
from cogs.ui.flag_views import FlagManageView

log = logging.getLogger("dayz-manager")


class FlagManagement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def flag_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        current = current.casefold()

        return [
            app_commands.Choice(
                name=flag,
                value=flag,
            )
            for flag in utils.FLAGS
            if current in flag.casefold()
        ][:25]

    def base_embed(
        self,
        title: str,
        description: str,
        color: int,
    ) -> discord.Embed:

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )

        embed.set_footer(
            text="DayZ Manager"
        )

        embed.timestamp = discord.utils.utcnow()

        return embed

    # =========================================================
    # ASSIGN
    # =========================================================

    @app_commands.command(
        name="assign",
        description="Assign a flag to a role for a server.",
    )
    @admin_only()
    @app_commands.choices(
        selected_map=MAP_CHOICES
    )
    @app_commands.describe(
        selected_map="Map for this flag.",
        server="Server name/identifier.",
        flag="Flag name.",
        role="Role to assign.",
    )
    @app_commands.autocomplete(
        flag=flag_autocomplete
    )
    async def assign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
        flag: str,
        role: discord.Role,
    ):

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True,
            )

        map_key = normalize_map(
            selected_map
        )

        server = utils.normalize_server(
            server
        )

        flag_name = utils.normalize_flag(
            flag
        )

        if not flag_name:
            return await interaction.response.send_message(
                f"❌ Invalid flag `{flag}`.",
                ephemeral=True,
            )

        # -----------------------------------------------------
        # Only prevent @everyone and managed/integration roles.
        #
        # IMPORTANT:
        # There is NO Faction- requirement here.
        #
        # /assign can therefore use:
        # Faction-Sand Monkeys
        # Police
        # Admin
        # Moderator
        # Event Team
        # etc.
        # -----------------------------------------------------

        if role.is_default() or role.managed:
            return await interaction.response.send_message(
                "❌ That role cannot be assigned to a flag.",
                ephemeral=True,
            )

        await interaction.response.defer(
            thinking=True
        )

        result = await utils.claim_flag(
            str(guild.id),
            map_key,
            server,
            flag_name,
            str(role.id),
        )

        if not result:
            return await interaction.followup.send(
                "⚠️ That flag is already claimed or does not exist for this setup.",
                ephemeral=True,
            )

        # -----------------------------------------------------
        # Refresh the public flag message.
        # -----------------------------------------------------

        view = FlagManageView(
            guild,
            map_key,
            server,
            self.bot,
        )

        await view.refresh_message()

        # -----------------------------------------------------
        # Confirmation embed.
        # -----------------------------------------------------

        embed = self.base_embed(
            "🏴 Flag Assigned",
            (
                f"**Flag:** `{flag_name}`\n"
                f"**Map:** `{map_key.title()}`\n"
                f"**Server:** `{server}`\n"
                f"**Role:** {role.mention}\n"
                f"**By:** {interaction.user.mention}"
            ),
            0x2ECC71,
        )

        await interaction.followup.send(
            embed=embed
        )

    # =========================================================
    # RELEASE
    # =========================================================

    @app_commands.command(
        name="release",
        description="Release a flag back to the available pool.",
    )
    @admin_only()
    @app_commands.choices(
        selected_map=MAP_CHOICES
    )
    @app_commands.describe(
        selected_map="Map containing the flag.",
        server="Server name/identifier.",
        flag="Flag to release.",
    )
    @app_commands.autocomplete(
        flag=flag_autocomplete
    )
    async def release_cmd(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
        flag: str,
    ):

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True,
            )

        map_key = normalize_map(
            selected_map
        )

        server = utils.normalize_server(
            server
        )

        flag_name = utils.normalize_flag(
            flag
        )

        if not flag_name:
            return await interaction.response.send_message(
                f"❌ Invalid flag `{flag}`.",
                ephemeral=True,
            )

        await interaction.response.defer(
            thinking=True
        )

        result = await utils.release_flag(
            str(guild.id),
            map_key,
            server,
            flag_name,
        )

        if not result:
            return await interaction.followup.send(
                "⚠️ That flag is already unclaimed or does not exist.",
                ephemeral=True,
            )

        # -----------------------------------------------------
        # Refresh the public flag message.
        # -----------------------------------------------------

        view = FlagManageView(
            guild,
            map_key,
            server,
            self.bot,
        )

        await view.refresh_message()

        # -----------------------------------------------------
        # Confirmation embed.
        # -----------------------------------------------------

        embed = self.base_embed(
            "🏳️ Flag Released",
            (
                f"**Flag:** `{flag_name}`\n"
                f"**Map:** `{map_key.title()}`\n"
                f"**Server:** `{server}`\n"
                f"**By:** {interaction.user.mention}"
            ),
            0x95A5A6,
        )

        await interaction.followup.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        FlagManagement(bot)
    )
