import discord
from discord import app_commands
from discord.ext import commands
import io
import json

class Teleporter(commands.Cog):
    """Generate teleporter JSON configuration files."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="teleporter",
        description="Generate teleporter JSON files for DayZ teleporters."
    )
    @app_commands.describe(
        position_a="First position array (e.g. [1234, 56, 789]) or comma-separated (1234,56,789)",
        position_b="Second position array (e.g. [9876, 54, 321]) or comma-separated (9876,54,321)"
    )
    async def teleporter(self, interaction: discord.Interaction, position_a: str, position_b: str):
        """
        Creates two teleporter JSON files using user-supplied coordinates.
        """
        await interaction.response.defer(ephemeral=True)

        # --- Normalize user input ---
        def normalize(pos: str):
            pos = pos.strip().replace(" ", "")
            if not pos.startswith("["):
                pos = f"[{pos}]"
            return json.loads(pos.replace(",,", ","))

        try:
            pos_a = normalize(position_a)
            pos_b = normalize(position_b)
        except Exception:
            await interaction.followup.send("❌ Invalid position format. Use `[x, y, z]` or `x,y,z`.", ephemeral=True)
            return

        # --- Build Teleporter JSON objects ---
        teleporter1 = {
            "areaName": "RestrictedAreaWarheadStorage",
            "PRABoxes": [[[1, 1, 1], [90, 0, 0], pos_a]],
            "safePositions3D": [pos_b],
            "_comment": "Teleporter1"
        }

        teleporter2 = {
            "areaName": "RestrictedAreaWarheadStorage",
            "PRABoxes": [[[1, 1, 1], [90, 0, 0], pos_b]],
            "safePositions3D": [pos_a],
            "_comment": "Teleporter2"
        }

        # --- Convert to JSON text ---
        json1 = json.dumps(teleporter1, indent=2)
        json2 = json.dumps(teleporter2, indent=2)

        # --- Create in-memory file objects ---
        file1 = discord.File(io.BytesIO(json1.encode("utf-8")), filename="Teleporter1.json")
        file2 = discord.File(io.BytesIO(json2.encode("utf-8")), filename="Teleporter2.json")

        # --- Send both files as attachments ---
        await interaction.followup.send(
            content="✅ Teleporter JSON files generated successfully!",
            files=[file1, file2],
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Teleporter(bot))
