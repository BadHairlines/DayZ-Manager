import discord
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

    @commands.has_permissions(administrator=True)
    @commands.command(name="assign")
    async def assign(self, ctx, map: str = None, flag: str = None, role: discord.Role = None):
        """Assign a flag to a role for a specific map."""
        if not map or not flag or not role:
            return await ctx.send("Usage: `!assign <map> <flag> <@role>`")

        map = map.lower()
        flag = flag.strip()

        def make_embed(title, desc, color):
            embed = discord.Embed(title=title, description=desc, color=color)
            embed.set_author(name="🪧 Assign Notification 🪧")
            embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
            return embed

        # Invalid map check
        if map not in VALID_MAPS:
            embed = make_embed("**ERROR**", "Invalid map specified. Please use `livonia`, `chernarus`, or `sakhal`.", 0xFF0000)
            return await ctx.send(embed=embed, delete_after=15)

        # Invalid flag check
        if flag not in VALID_FLAGS:
            embed = make_embed("**DOESN'T EXIST**", f"The **{flag} Flag** does not exist on **{map.title()}** lol.", 0xFF0000)
            return await ctx.send(embed=embed, delete_after=15)

        # Ensure structure exists
        if map not in data:
            data[map] = {}
        if flag not in data[map]:
            data[map][flag] = {"assigned": False, "role_id": None}

        # Already assigned?
        if data[map][flag]["assigned"]:
            embed = make_embed("**ALREADY ASSIGNED**", f"The **{flag} Flag** is already assigned on **{map.title()}**.", 0xFF0000)
            return await ctx.send(embed=embed, delete_after=15)

        # Assign
        data[map][flag] = {"assigned": True, "role_id": role.id}
        save_data(data)

        embed = make_embed("**ASSIGNED**",
            f"The **{flag} Flag** has been marked as ❌ on **{map.title()}** and assigned to {role.mention}.",
            0x86DC3D
        )
        await ctx.send(embed=embed, delete_after=15)

async def setup(bot):
    await bot.add_cog(Assign(bot))
