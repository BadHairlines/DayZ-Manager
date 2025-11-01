import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import reset_map_flags, MAP_DATA, FLAGS  # uses new db helper
import asyncpg

class Reset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🧹 Reset Notification 🧹")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        return embed

    @app_commands.command(name="reset", description="Reset all flags for a selected map back to ✅.")
    @app_commands.describe(selected_map="Select the map to reset (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def reset(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value

        try:
            # reset all flags in the database for this guild & map
            await reset_map_flags(guild_id, map_key)
        except asyncpg.PostgresError as e:
            embed = self.make_embed("❌ Database Error", f"Could not reset flags:\n```{e}```", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = self.make_embed(
            "**RESET COMPLETE**",
            f"✅ All flags for **{MAP_DATA[map_key]['name']}** have been reset to ✅ and all role assignments cleared.",
            0x00FF00
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Reset(bot))
