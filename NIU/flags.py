import discord
from discord import app_commands, Interaction
from discord.ext import commands
from cogs.helpers.decorators import MAP_CHOICES
from cogs.utils import MAP_DATA, get_all_flags, create_flag_embed, log_action


class Flags(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="flags",
        description="View all flags and their status for a specific map."
    )
    @app_commands.describe(selected_map="Select the map to view flags")
    @app_commands.choices(selected_map=MAP_CHOICES)  # ✅ shared map choices
    async def flags(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        """Display all flag statuses for the selected map."""
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]

        # ✅ Fetch flag records
        records = await get_all_flags(guild_id, map_key)
        if not records:
            await interaction.response.send_message(
                f"🚫 **{map_info['name']}** hasn’t been set up yet or has no data.\n"
                f"Run `/setup` first to initialize this map.",
                ephemeral=True
            )

            # 🪵 Structured log for missing data
            await log_action(
                guild,
                map_key,
                title="Flags View Failed",
                description=(
                    f"🚫 {interaction.user.mention} tried to view **{map_info['name']}**, "
                    "but it has not been set up yet."
                ),
                color=0xE74C3C
            )
            return

        # ✅ Use centralized embed builder
        embed = await create_flag_embed(guild_id, map_key)
        await interaction.response.send_message(embed=embed)

        # 🪵 Structured view log
        await log_action(
            guild,
            map_key,
            title="Flags Viewed",
            description=(
                f"👁️ {interaction.user.mention} viewed all flags for **{map_info['name']}**.\n"
                f"Displayed {len(records)} total flags in live status."
            ),
            color=0x3498DB
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Flags(bot))
