import discord
from discord import app_commands
from discord.ext import commands

from cogs.helpers.decorators import (
    admin_only,
    MAP_CHOICES,
    normalize_map
)

from cogs import utils
from cogs.ui_views import FlagManageView


class FlagManagement(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------
    # AUTOCOMPLETE
    # -----------------------------
    async def flag_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ):

        current = current.lower()

        return [
            app_commands.Choice(
                name=f,
                value=f
            )
            for f in utils.FLAGS
            if current in f.lower()
        ][:25]

    # -----------------------------
    # BASE EMBED
    # -----------------------------
    def _base_embed(
        self,
        title: str,
        color: int
    ):

        embed = discord.Embed(
            title=title,
            color=color
        )

        embed.set_footer(
            text="Flag System"
        )

        embed.timestamp = discord.utils.utcnow()

        return embed

    # =========================================================
    # ASSIGN
    # =========================================================
    @app_commands.command(
        name="assign",
        description="Assign a flag to a role for a server."
    )
    @admin_only()
    @app_commands.choices(
        selected_map=MAP_CHOICES
    )
    @app_commands.describe(
        selected_map="Map for this flag.",
        server="Server name/identifier.",
        flag="Flag name.",
        role="Role to assign."
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
        role: discord.Role
    ):

        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True
            )

        await interaction.response.defer(
            thinking=True
        )

        guild = interaction.guild

        map_key = normalize_map(
            selected_map.value
        )

        server = utils.normalize_server(server)

        flag_name = utils.normalize_flag(flag)

        if not flag_name:
            return await interaction.followup.send(
                f"❌ Invalid flag `{flag}`.",
                ephemeral=True
            )

        try:

            await utils.set_flag(
                str(guild.id),
                map_key,
                server,
                flag_name,
                "❌",
                str(role.id)
            )

            view = FlagManageView(
                guild,
                map_key,
                server,
                self.bot
            )

            await view.refresh_flag_embed()

        except Exception as e:

            return await interaction.followup.send(
                f"❌ Error assigning flag:\n"
                f"```{type(e).__name__}: {e}```",
                ephemeral=True
            )

        embed = self._base_embed(
            "Flag Assigned",
            0x2ECC71
        )

        embed.description = (
            f"🏳️ **Flag:** `{flag_name}`\n"
            f"🗺️ **Map:** `{map_key}`\n"
            f"🖥️ **Server:** `{server}`\n"
            f"🎭 **Role:** {role.mention}\n"
            f"👤 **By:** {interaction.user.mention}"
        )

        await interaction.followup.send(
            embed=embed
        )

    # =========================================================
    # RELEASE
    # =========================================================
    @app_commands.command(
        name="release",
        description="Release a flag back to the available pool."
    )
    @admin_only()
    @app_commands.choices(
        selected_map=MAP_CHOICES
    )
    @app_commands.describe(
        selected_map="Map containing flag.",
        server="Server name/identifier.",
        flag="Flag to release."
    )
    @app_commands.autocomplete(
        flag=flag_autocomplete
    )
    async def release_cmd(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        server: str,
        flag: str
    ):

        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True
            )

        await interaction.response.defer(
            thinking=True
        )

        guild = interaction.guild

        map_key = normalize_map(
            selected_map.value
        )

        server = utils.normalize_server(server)

        flag_name = utils.normalize_flag(flag)

        if not flag_name:
            return await interaction.followup.send(
                f"❌ Invalid flag `{flag}`.",
                ephemeral=True
            )

        try:

            await utils.release_flag(
                str(guild.id),
                map_key,
                server,
                flag_name
            )

            view = FlagManageView(
                guild,
                map_key,
                server,
                self.bot
            )

            await view.refresh_flag_embed()

        except Exception as e:

            return await interaction.followup.send(
                f"❌ Error releasing flag:\n"
                f"```{type(e).__name__}: {e}```",
                ephemeral=True
            )

        embed = self._base_embed(
            "Flag Released",
            0x95A5A6
        )

        embed.description = (
            f"🏳️ **Flag:** `{flag_name}`\n"
            f"🗺️ **Map:** `{map_key}`\n"
            f"🖥️ **Server:** `{server}`\n"
            f"👤 **By:** {interaction.user.mention}"
        )

        await interaction.followup.send(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        FlagManagement(bot)
    )
