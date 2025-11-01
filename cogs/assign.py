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

VALID_FLAGS = [
    "APA", "Altis", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals",
    "Chedaki", "CHEL", "CMC", "HunterZ", "NAPA", "Rooster", "TEC", "UEC",
    "Wolf", "Zenit", "Crook", "NSahrani", "Pirates", "Rex", "Refuge", "RSTA",
    "Snake", "Zagorky"
]

VALID_MAPS = ["livonia", "chernarus", "sakhal"]

class Assign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🪧 Assign Notification 🪧")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    # ===============================
    # Autocomplete Functions
    # ===============================
    async def map_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=m.title(), value=m)
            for m in VALID_MAPS if current.lower() in m.lower()
        ]

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=f, value=f)
            for f in VALID_FLAGS if current.lower() in f.lower()
        ][:25]  # limit for Discord

    # ===============================
    # /assign
    # ===============================
    @app_commands.command(name="assign", description="Assign a flag to a role for a specific map.")
    @app_commands.describe(map="Select the map", flag="Select the flag", role="Select the role to assign it to")
    @app_commands.autocomplete(map=map_autocomplete, flag=flag_autocomplete)
    async def assign(self, interaction: discord.Interaction, map: str, flag: str, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
            return

        map = map.lower()
        flag = flag.strip()

        if map not in VALID_MAPS:
            embed = self.make_embed("**ERROR**", "Invalid map specified. Please use Livonia, Chernarus, or Sakhal.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if flag not in VALID_FLAGS:
            embed = self.make_embed("**DOESN'T EXIST**", f"The **{flag} Flag** does not exist on **{map.title()}** lol.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if map not in data:
            data[map] = {}
        if flag not in data[map]:
            data[map][flag] = {"assigned": False, "role_id": None}

        if data[map][flag]["assigned"]:
            embed = self.make_embed("**ALREADY ASSIGNED**", f"The **{flag} Flag** is already assigned on **{map.title()}**.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        data[map][flag] = {"assigned": True, "role_id": role.id}
        save_data(data)

        embed = self.make_embed("**ASSIGNED**",
            f"The **{flag} Flag** has been marked as ❌ on **{map.title()}** and assigned to {role.mention}.",
            0x86DC3D
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Assign(bot))
