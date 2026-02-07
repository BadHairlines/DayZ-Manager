import logging
import discord
from discord import app_commands
from discord.ext import commands

from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.helpers.flag_manager import FlagManager
from cogs.utils import FLAGS

log = logging.getLogger("dayz-manager")


class FlagManagement(commands.Cog, BaseCog):
    """Handles assigning and releasing flags."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Provides autocomplete for flag names."""
        results = [f for f in FLAGS if current.lower() in f.lower()]
        return [app_commands.Choice(name=f, value=f) for f in results[:25]]

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
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def assign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str,
        role: discord.Role
    ):
        await interaction.response.defer(thinking=True)

        if not interaction.guild:
            return await interaction.followup.send(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )

        guild = interaction.guild
        map_key = normalize_map(selected_map)
        flag = flag.strip().title()

        try:
            await FlagManager.assign_flag(guild, map_key, flag, role, interaction.user)
        except ValueError as err:
            return await interaction.followup.send(str(err), ephemeral=True)
        except Exception as e:
            log.warning(f"Error assigning flag '{flag}' in {guild.name}: {e}")
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
        embed.set_footer(text="DayZ Manager • Flag Assignment")
        embed.timestamp = discord.utils.utcnow()

        log.info(
            f"✅ Flag '{flag}' assigned to {role.name} on map {map_key} "
            f"by {interaction.user} in {guild.name}."
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="release",
        description="Release a claimed flag and make it available again."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Select the map containing the flag to release",
        flag="Enter the flag name to release (e.g. Wolf, NAPA, APA)"
    )
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def release(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str
    ):
        await interaction.response.defer(thinking=True)

        if not interaction.guild:
            return await interaction.followup.send(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )

        guild = interaction.guild
        map_key = normalize_map(selected_map)
        flag = flag.strip().title()

        try:
            await FlagManager.release_flag(guild, map_key, flag, interaction.user)
        except ValueError as err:
            return await interaction.followup.send(str(err), ephemeral=True)
        except Exception as e:
            log.warning(f"Error releasing flag '{flag}' in {guild.name}: {e}")
            return await interaction.followup.send(
                f"❌ Unexpected error releasing flag:\n```{e}```",
                ephemeral=True
            )

        embed = self.make_embed(
            title="✅ Flag Released",
            desc=(
                f"🏳️ **Flag:** `{flag}`\n"
                f"🗺️ **Map:** `{map_key.title()}`\n"
                f"👤 **Released by:** {interaction.user.mention}"
            ),
            color=0x95A5A6,
            author_icon="🏁",
            author_name="Flag Release"
        )
        embed.set_footer(text="DayZ Manager • Flag Release")
        embed.timestamp = discord.utils.utcnow()

        log.info(
            f"✅ Flag '{flag}' released by {interaction.user} "
            f"on map {map_key} in {guild.name}."
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(FlagManagement(bot))
