import discord
from discord import app_commands
from discord.ext import commands
import json
import os

DATA_FILE = "server_vars.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

VALID_MAPS = ["livonia", "chernarus", "sakhal"]

class Reset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🧹 Reset Notification 🧹")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    @app_commands.command(name="reset", description="Reset all flags for a selected map back to ✅.")
    @app_commands.describe(map="The map (livonia, chernarus, sakhal)")
    async def reset(self, interaction: discord.Interaction, map: str):
        # Only allow admins
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
            return

        map = map.lower()

        # Validate map
        if map not in VALID_MAPS:
            embed = self.make_embed("**ERROR**", "Invalid map specified. Please use `livonia`, `chernarus`, or `sakhal`.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # If map not found
        if map not in data:
            embed = self.make_embed("**NOT SET UP**", f"❌ {map.title()} has not been set up yet! Run `/setup` first.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Reset all flags
        for flag in data[map].keys():
            data[map][flag] = {"assigned": False, "role_id": None}

        save_data(data)

        embed = self.make_embed(
            "**RESET COMPLETE**",
            f"✅ All flags for **{map.title()}** have been reset to ✅ and roles cleared.",
            0x00FF00
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Reset(bot))
