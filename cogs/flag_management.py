import discord
from discord import app_commands
from discord.ext import commands

from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.helpers.flag_manager import FlagManager
from cogs.utils import FLAGS


class FlagManagement(commands.Cog, BaseCog):
    """Handles assigning and releasing flags."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- AUTOCOMPLETE ----------------

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Provides autocomplete for flag names."""
        current = current.lower()
        matches = [f for f in FLAGS if current in f.lower()]
        return [
            app_commands.Choice(name=f, value=f)
            for f in matches[:25]
        ]

    # ---------------- ASSIGN ----------------

    @app_commands.command(
        name="assign",
        description="Assign a flag to a faction or role for a selected map."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Select which map this flag belongs to",
        flag="Flag name (e.g. Wolf, APA, NAPA)",
        role="Role to assign the flag to"
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
            return await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        map_key = normalize_map(selected_map.value)
        flag_name = flag.strip().title()

        if flag_name not in FLAGS:
            return await interaction.followup.send(
                f"❌ Invalid flag `{flag_name}`.",
                ephemeral=True
            )

        try:
            await FlagManager.assign_flag(
                guild,
                map_key,
                flag_name,
                role,
                interaction.user
            )

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
                f"🏳️ **Flag:** `{flag_name}`\n"
                f"🗺️ **Map:** `{map_key.title()}`\n"
                f"🎭 **Assigned To:** {role.mention}\n"
                f"👤 **By:** {interaction.user.mention}"
            ),
            color=0x2ECC71,
            author_icon="🏴",
            author_name="Flag Assignment"
        )

        embed.set_footer(text="DayZ Manager • Flag System")
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed)

    # ---------------- RELEASE ----------------

    @app_commands.command(
        name="release",
        description="Release a claimed flag back into the pool."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Map containing the flag",
        flag="Flag name to release (e.g. Wolf, NAPA, APA)"
    )
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def release(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        map_key = normalize_map(selected_map.value)
        flag_name = flag.strip().title()

        if flag_name not in FLAGS:
            return await interaction.followup.send(
                f"❌ Invalid flag `{flag_name}`.",
                ephemeral=True
            )

        try:
            await FlagManager.release_flag(
                guild,
                map_key,
                flag_name,
                interaction.user
            )

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
                f"🏳️ **Flag:** `{flag_name}`\n"
                f"🗺️ **Map:** `{map_key.title()}`\n"
                f"👤 **Released By:** {interaction.user.mention}"
            ),
            color=0x95A5A6,
            author_icon="🏁",
            author_name="Flag Release"
        )

        embed.set_footer(text="DayZ Manager • Flag System")
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(FlagManagement(bot))
