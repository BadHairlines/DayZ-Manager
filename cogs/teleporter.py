import discord
from discord import app_commands
from discord.ext import commands
import io
import json
import asyncio
import re

class Teleporter(commands.Cog):
    """Generate teleporter JSON configuration files."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="teleporter",
        description="Generate 1-way or 2-way teleporter JSON files for DayZ teleporters."
    )
    @app_commands.describe(
        position_a="First position array (e.g. [1234,56,789]) or comma-separated (1234,56,789)",
        position_b="Second position array (e.g. [9876,54,321]) or comma-separated (9876,54,321)",
        name="Base teleporter name (e.g. Base2NWAF)"
    )
    async def teleporter(
        self,
        interaction: discord.Interaction,
        position_a: str,
        position_b: str,
        name: str
    ):
        """
        Creates two teleporter JSON files using user-supplied coordinates.
        Automatically reverses the name for the second file.
        """
        await interaction.response.defer(ephemeral=True)

        # Show a temporary progress message
        progress_msg = await interaction.followup.send(
            "⚙️ Generating teleporter JSON files, please wait...",
            ephemeral=True
        )

        # --- Normalize position inputs ---
        def normalize(pos: str):
            pos = pos.strip().replace(" ", "")
            if not pos.startswith("["):
                pos = f"[{pos}]"
            return json.loads(pos.replace(",,", ","))

        try:
            pos_a = normalize(position_a)
            pos_b = normalize(position_b)
        except Exception:
            await progress_msg.edit(
                content="❌ Invalid position format. Use `[x, y, z]` or `x,y,z`."
            )
            return

        # --- Handle name swapping (e.g. Base2NWAF -> NWAF2Base) ---
        def swap_name(base_name: str) -> str:
            # Split at the first '2' or 'To' (case-insensitive)
            match = re.split(r'2|to', base_name, maxsplit=1, flags=re.IGNORECASE)
            if len(match) == 2:
                part1, part2 = match
                return f"{part2}2{part1}" if part2 and part1 else f"{base_name}_Reversed"
            return f"{base_name}_Reversed"

        name_a_to_b = name.replace(" ", "_")
        name_b_to_a = swap_name(name_a_to_b)

        # --- Build JSON structures ---
        teleporter1 = {
            "areaName": "RestrictedAreaWarheadStorage",
            "PRABoxes": [[[1, 1, 1], [90, 0, 0], pos_a]],
            "safePositions3D": [pos_b],
            "_comment": f"Teleporter from A→B ({name_a_to_b})"
        }

        teleporter2 = {
            "areaName": "RestrictedAreaWarheadStorage",
            "PRABoxes": [[[1, 1, 1], [90, 0, 0], pos_b]],
            "safePositions3D": [pos_a],
            "_comment": f"Teleporter from B→A ({name_b_to_a})"
        }

        # --- Convert to JSON text ---
        json1 = json.dumps(teleporter1, indent=2)
        json2 = json.dumps(teleporter2, indent=2)

        # --- File names ---
        file1_name = f"Teleporter_{name_a_to_b}.json"
        file2_name = f"Teleporter_{name_b_to_a}.json"

        # --- Create in-memory files ---
        file1 = discord.File(io.BytesIO(json1.encode("utf-8")), filename=file1_name)
        file2 = discord.File(io.BytesIO(json2.encode("utf-8")), filename=file2_name)

        await asyncio.sleep(1.2)

        # --- Edit message to show success ---
        await progress_msg.edit(
            content=(
                f"✅ Teleporter JSON files generated successfully!\n"
                f"📄 `{file1_name}`\n"
                f"📄 `{file2_name}`"
            ),
            attachments=[file1, file2]
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Teleporter(bot))
