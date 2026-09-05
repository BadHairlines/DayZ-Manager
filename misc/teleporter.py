from __future__ import annotations

import asyncio
import io
import json

import discord
from discord import app_commands
from discord.ext import commands



class Teleporter(commands.Cog):
    """Generate 2-way teleporter JSON configuration files."""

    def __init__(self, bot):
        self.bot = bot

    # =========================================================
    # TELEPORTER COMMAND
    # =========================================================

    @app_commands.command(
        name="teleporter",
        description="Generate 2-way teleporter JSON files for a faction."
    )
    @app_commands.guild_only()
    @app_commands.describe(
        faction_name="Faction name (e.g. Wolf)",
        location_a_name="Name of Location A (e.g. NWAF)",
        location_b_name="Name of Location B (e.g. Tisy)",
        location_a="Coordinates for Location A: [x,y,z] or x,y,z",
        location_b="Coordinates for Location B: [x,y,z] or x,y,z",
    )
    async def teleporter(
        self,
        interaction: discord.Interaction,
        faction_name: str,
        location_a_name: str,
        location_b_name: str,
        location_a: str,
        location_b: str,
    ):
        """
        Creates two teleporter JSON files:

        Location A → Location B
        Location B → Location A
        """

        await interaction.response.defer(ephemeral=True)

        # =====================================================
        # PROGRESS MESSAGE
        # =====================================================

        progress_msg = await interaction.followup.send(
            "⚙️ Generating teleporter JSON files, please wait...",
            ephemeral=True,
        )

        # =====================================================
        # NORMALIZE COORDINATES
        # =====================================================

        def normalize_position(position: str):
            position = position.strip().replace(" ", "")

            if not position.startswith("["):
                position = f"[{position}]"

            data = json.loads(position)

            if not isinstance(data, list) or len(data) != 3:
                raise ValueError("Position must contain exactly 3 coordinates.")

            # Make sure all coordinates are numbers
            for value in data:
                if not isinstance(value, (int, float)):
                    raise ValueError("Coordinates must be numbers.")

            return data

        try:
            pos_a = normalize_position(location_a)
            pos_b = normalize_position(location_b)

        except Exception:
            await progress_msg.edit(
                content=(
                    "❌ **Invalid coordinate format.**\n\n"
                    "Use either:\n"
                    "`[1234, 56, 789]`\n"
                    "or\n"
                    "`1234,56,789`"
                )
            )
            return

        # =====================================================
        # CLEAN NAMES
        # =====================================================

        def clean_name(value: str) -> str:
            """
            Converts names into safe filename-friendly names.
            """

            value = value.strip()

            # Replace spaces with underscores
            value = value.replace(" ", "_")

            # Keep only letters, numbers, underscores and hyphens
            value = "".join(
                character
                for character in value
                if character.isalnum() or character in "_-"
            )

            return value or "Unknown"

        faction = clean_name(faction_name)
        location_a_clean = clean_name(location_a_name)
        location_b_clean = clean_name(location_b_name)

        # =====================================================
        # FILE NAMES
        # =====================================================

        file1_name = (
            f"Teleporter_{faction}_"
            f"{location_a_clean}_to_{location_b_clean}.json"
        )

        file2_name = (
            f"Teleporter_{faction}_"
            f"{location_b_clean}_to_{location_a_clean}.json"
        )

        # =====================================================
        # TELEPORTER A → B
        # =====================================================

        teleporter1 = {
            "areaName": "RestrictedAreaWarheadStorage",
            "PRABoxes": [
                [
                    [1, 1, 1],
                    [90, 0, 0],
                    pos_a,
                ]
            ],
            "safePositions3D": [
                pos_b
            ],
            "_comment": (
                f"{faction}: "
                f"{location_a_name} → {location_b_name}"
            ),
        }

        # =====================================================
        # TELEPORTER B → A
        # =====================================================

        teleporter2 = {
            "areaName": "RestrictedAreaWarheadStorage",
            "PRABoxes": [
                [
                    [1, 1, 1],
                    [90, 0, 0],
                    pos_b,
                ]
            ],
            "safePositions3D": [
                pos_a
            ],
            "_comment": (
                f"{faction}: "
                f"{location_b_name} → {location_a_name}"
            ),
        }

        # =====================================================
        # CONVERT TO JSON
        # =====================================================

        json1 = json.dumps(
            teleporter1,
            indent=2
        )

        json2 = json.dumps(
            teleporter2,
            indent=2
        )

        # =====================================================
        # CREATE FILES IN MEMORY
        # =====================================================

        file1 = discord.File(
            io.BytesIO(json1.encode("utf-8")),
            filename=file1_name,
        )

        file2 = discord.File(
            io.BytesIO(json2.encode("utf-8")),
            filename=file2_name,
        )

        # =====================================================
        # UX DELAY
        # =====================================================

        await asyncio.sleep(1.2)

        # =====================================================
        # COPY / PASTE CONFIG PATHS
        # =====================================================

        copy_lines = (
            "```c\n"
            f'    "./custom/{file1_name}",\n'
            f'    "./custom/{file2_name}",\n'
            "```"
        )

        # =====================================================
        # FINAL RESPONSE
        # =====================================================

        await progress_msg.edit(
            content=(
                "✅ **Teleporter JSON files generated successfully!**\n\n"
                f"🏴 **Faction:** `{faction_name}`\n"
                f"📍 **Location A:** `{location_a_name}`\n"
                f"📍 **Location B:** `{location_b_name}`\n\n"
                f"🔵 **A → B:** `{location_a_name} → {location_b_name}`\n"
                f"🔴 **B → A:** `{location_b_name} → {location_a_name}`\n\n"
                f"📄 `{file1_name}`\n"
                f"📄 `{file2_name}`\n\n"
                f"**Copy & Paste into your config:**\n"
                f"{copy_lines}"
            ),
            attachments=[
                file1,
                file2,
            ],
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(Teleporter(bot))
