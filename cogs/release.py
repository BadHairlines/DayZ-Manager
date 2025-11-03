import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.helpers.flag_manager import FlagManager


class Release(commands.Cog, BaseCog):
    """Release a claimed flag and make it available again."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
    async def release(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str
    ):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        map_key = normalize_map(selected_map)

        try:
            await FlagManager.release_flag(guild, map_key, flag, interaction.user)
        except ValueError as err:
            return await interaction.followup.send(str(err), ephemeral=True)
        except Exception as e:
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
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Release(bot))
