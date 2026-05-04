# cogs/flag_management.py

import discord
from discord import app_commands
from discord.ext import commands

from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.utils import FLAGS, set_flag, release_flag


class FlagManagement(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=f, value=f)
            for f in FLAGS if current.lower() in f.lower()
        ][:25]

    def _is_valid_flag(self, flag: str) -> bool:
        return flag in FLAGS

    # ---------------- ASSIGN ----------------
    @app_commands.command(name="assign")
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def assign(self, interaction, selected_map, flag: str, role: discord.Role):

        await interaction.response.defer(thinking=True)

        map_key = normalize_map(selected_map.value)
        flag_name = flag.strip().title()

        if not self._is_valid_flag(flag_name):
            return await interaction.followup.send("❌ Invalid flag.", ephemeral=True)

        await set_flag(
            str(interaction.guild.id),
            map_key,
            flag_name,
            "❌",  # ✅ FIXED
            str(role.id)  # ✅ FIXED
        )

        await interaction.followup.send(
            f"🏴 **{flag_name} → {role.mention}** assigned."
        )

    # ---------------- RELEASE ----------------
    @app_commands.command(name="release")
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def release_cmd(self, interaction, selected_map, flag: str):

        await interaction.response.defer(thinking=True)

        map_key = normalize_map(selected_map.value)
        flag_name = flag.strip().title()

        if not self._is_valid_flag(flag_name):
            return await interaction.followup.send("❌ Invalid flag.", ephemeral=True)

        await release_flag(
            str(interaction.guild.id),
            map_key,
            flag_name
        )

        await interaction.followup.send(f"🏳️ **{flag_name} released**")


async def setup(bot: commands.Bot):
    await bot.add_cog(FlagManagement(bot))
