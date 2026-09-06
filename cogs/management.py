from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs import utils
from cogs.decorators import MAP_CHOICES, admin_only, normalize_map
from cogs.ui.flag_views import FlagManageView
from cogs.ui.gear_views import GearManageView

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
        selected = getattr(interaction.namespace, "system_type", None)
        claim_type = utils.normalize_system_type(
            getattr(selected, "value", selected) or "flags"
        )
        items = utils.system_items(claim_type) or utils.FLAGS
        return [
            app_commands.Choice(name=item, value=item)
            for item in items
            if current in item.casefold()
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
        selected_map=MAP_CHOICES,
        system_type=[
            app_commands.Choice(name="🚩 Flags", value="flags"),
            app_commands.Choice(name="🧥 Raincoats", value="raincoats"),
            app_commands.Choice(name="🎽 Armbands", value="armbands"),
        ],
    )
    @app_commands.describe(
        selected_map="Map for this flag.",
        server="Server name/identifier.",
        flag="Flag / raincoat / armband option.",
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
        system_type: app_commands.Choice[str],
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

        claim_type = utils.normalize_system_type(system_type.value)
        flag_name = (
            utils.normalize_flag(flag)
            if claim_type == "flags"
            else utils.normalize_system_item(claim_type, flag)
        )

        if not flag_name:
            return await interaction.response.send_message(
                f"❌ Invalid option `{flag}` for `{claim_type}`.",
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

        result = await utils.claim_system_item(
            str(guild.id), map_key, server, claim_type,
            flag_name, str(role.id),
            actor_id=str(interaction.user.id), source="slash:/assign",
        )

        if not result:
            return await interaction.followup.send(
                "⚠️ That flag is already claimed or does not exist for this setup.",
                ephemeral=True,
            )

        # -----------------------------------------------------
        # Refresh the public flag message.
        # -----------------------------------------------------

        if claim_type == "flags":
            view = await FlagManageView.create(guild, map_key, server, self.bot)
        else:
            view = await GearManageView.create(
                guild, map_key, server, claim_type, self.bot
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
        selected_map=MAP_CHOICES,
        system_type=[
            app_commands.Choice(name="🚩 Flags", value="flags"),
            app_commands.Choice(name="🧥 Raincoats", value="raincoats"),
            app_commands.Choice(name="🎽 Armbands", value="armbands"),
        ],
    )
    @app_commands.describe(
        selected_map="Map containing the flag.",
        server="Server name/identifier.",
        flag="Flag / raincoat / armband option to release.",
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
        system_type: app_commands.Choice[str],
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

        claim_type = utils.normalize_system_type(system_type.value)
        flag_name = (
            utils.normalize_flag(flag)
            if claim_type == "flags"
            else utils.normalize_system_item(claim_type, flag)
        )

        if not flag_name:
            return await interaction.response.send_message(
                f"❌ Invalid option `{flag}` for `{claim_type}`.",
                ephemeral=True,
            )

        await interaction.response.defer(
            thinking=True
        )

        result = await utils.release_system_item(
            str(guild.id), map_key, server, claim_type,
            flag_name, actor_id=str(interaction.user.id), source="slash:/release",
        )

        if not result:
            return await interaction.followup.send(
                "⚠️ That flag is already unclaimed or does not exist.",
                ephemeral=True,
            )

        # -----------------------------------------------------
        # Refresh the public flag message.
        # -----------------------------------------------------

        if claim_type == "flags":
            view = await FlagManageView.create(guild, map_key, server, self.bot)
        else:
            view = await GearManageView.create(
                guild, map_key, server, claim_type, self.bot
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
