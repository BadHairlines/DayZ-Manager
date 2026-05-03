import discord
from discord import app_commands
from discord.ext import commands

from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.utils import FLAGS, set_flag, release_flag


class FlagManagement(commands.Cog):
    """Simple flag assignment system (role-based)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- AUTOCOMPLETE ----------------
    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()

        return [
            app_commands.Choice(name=f, value=f)
            for f in FLAGS
            if current in f.lower()
        ][:25]

    # ---------------- HELPERS ----------------
    def _is_valid_flag(self, flag: str) -> bool:
        return flag in FLAGS

    def _base_embed(self, title: str, color: int):
        embed = discord.Embed(title=title, color=color)
        embed.set_footer(text="Flag System")
        embed.timestamp = discord.utils.utcnow()
        return embed

    # ---------------- ASSIGN ----------------
    @app_commands.command(
        name="assign",
        description="Assign a flag to a role for a selected map."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Map for this flag",
        flag="Flag name",
        role="Role to assign"
    )
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def assign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str,
        role: discord.Role
    ):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        map_key = normalize_map(selected_map.value)
        flag_name = flag.strip().title()

        if not self._is_valid_flag(flag_name):
            return await interaction.followup.send(
                f"❌ Invalid flag `{flag_name}`.",
                ephemeral=True
            )

        try:
            await set_flag(guild.id, map_key, flag_name, "ASSIGNED", role.id)
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Error assigning flag:\n```{e}```",
                ephemeral=True
            )

        embed = self._base_embed("Flag Assigned", 0x2ECC71)
        embed.description = (
            f"🏳️ Flag: `{flag_name}`\n"
            f"🗺️ Map: `{map_key}`\n"
            f"🎭 Role: {role.mention}\n"
            f"👤 By: {interaction.user.mention}"
        )

        await interaction.followup.send(embed=embed)

    # ---------------- RELEASE ----------------
    @app_commands.command(
        name="release",
        description="Release a flag back to available pool."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Map containing flag",
        flag="Flag to release"
    )
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def release_cmd(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str
    ):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        map_key = normalize_map(selected_map.value)
        flag_name = flag.strip().title()

        if not self._is_valid_flag(flag_name):
            return await interaction.followup.send(
                f"❌ Invalid flag `{flag_name}`.",
                ephemeral=True
            )

        try:
            await release_flag(guild.id, map_key, flag_name)
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Error releasing flag:\n```{e}```",
                ephemeral=True
            )

        embed = self._base_embed("Flag Released", 0x95A5A6)
        embed.description = (
            f"🏳️ Flag: `{flag_name}`\n"
            f"🗺️ Map: `{map_key}`\n"
            f"👤 By: {interaction.user.mention}"
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(FlagManagement(bot))
