import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.helpers.flag_manager import FlagManager  # ✅ NEW
import asyncio

class Assign(commands.Cog, BaseCog):
    """Assign a flag to a faction or role."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="assign",
        description="Assign a flag to a specific faction or role for a chosen map."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Select which map this flag belongs to",
        flag="Enter the flag name to assign (e.g. Wolf, APA, NAPA)",
        role="Select the role or faction to assign the flag to"
    )
    async def assign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str,
        role: discord.Role
    ):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        map_key = normalize_map(selected_map)

        try:
            await FlagManager.assign_flag(guild, map_key, flag, role, interaction.user)
        except ValueError as err:
            return await interaction.followup.send(str(err), ephemeral=True)
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Unexpected error assigning flag:\n```{e}```",
                ephemeral=True
            )

        embed = self.make_embed(
            title="✅ Flag Assigned",
            desc=(
                f"🏳️ **Flag:** `{flag}`\n"
                f"🗺️ **Map:** `{map_key.title()}`\n"
                f"🎭 **Assigned to:** {role.mention}\n"
                f"👤 **By:** {interaction.user.mention}"
            ),
            color=0x2ECC71,
            author_icon="🏴",
            author_name="Flag Assignment"
        )

        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Assign(bot))
