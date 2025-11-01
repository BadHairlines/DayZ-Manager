import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import server_vars, save_data, FLAGS, MAP_DATA

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
        # Only allow admins
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You must be an administrator to use this command.",
                ephemeral=True
            )
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value
        guild_data = server_vars.get(guild_id)

        # Check if map setup exists
        if not guild_data or map_key not in guild_data:
            embed = self.make_embed(
                "**NOT SET UP**",
                f"❌ {MAP_DATA[map_key]['name']} has not been set up yet! Run `/setup` first.",
                0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Reset all flags on this map
        for flag in FLAGS:
            guild_data[f"{map_key}_{flag}"] = "✅"
            guild_data.pop(f"{map_key}_{flag}_role", None)

        await save_data()

        embed = self.make_embed(
            "**RESET COMPLETE**",
            f"✅ All flags for **{MAP_DATA[map_key]['name']}** have been reset to ✅ and all role assignments cleared.",
            0x00FF00
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Reset(bot))
