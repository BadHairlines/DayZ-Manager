import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import MAP_DATA, get_all_flags, create_flag_embed


class Flags(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="flags",
        description="View all flags and their status for a specific map."
    )
    @app_commands.describe(selected_map="Select the map to view flags")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def flags(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        """Display all flag statuses for the selected map."""
        guild_id = str(interaction.guild.id)
        map_key = selected_map.value

        # ✅ Check if any records exist first
        records = await get_all_flags(guild_id, map_key)
        if not records:
            await interaction.response.send_message(
                f"🚫 **{MAP_DATA[map_key]['name']}** hasn’t been set up yet or has no data.\n"
                f"Run `/setup` first to initialize this map.",
                ephemeral=True
            )
            return

        # ✅ Use centralized embed builder
        embed = await create_flag_embed(guild_id, map_key)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Flags(bot))
