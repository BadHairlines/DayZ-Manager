import discord
from discord import app_commands
from discord.ext import commands
import asyncio


class Vehicle(commands.Cog):
    """Generate DayZ vehicle event and spawn position XML configurations."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="vehicle",
        description="Generate a DayZ vehicle event and spawn position XML."
    )
    @app_commands.describe(
        name="Vehicle name (e.g. Taco — Vehicle is added automatically)",
        vehicle="Vehicle classname",
        x="X coordinate",
        z="Z coordinate"
    )
    @app_commands.choices(
        vehicle=[
            app_commands.Choice(name="🚤 Boat - Black", value="Boat_01_Black"),
            app_commands.Choice(name="🚤 Boat - Blue", value="Boat_01_Blue"),
            app_commands.Choice(name="🚤 Boat - Camo", value="Boat_01_Camo"),
            app_commands.Choice(name="🚤 Boat - Orange", value="Boat_01_Orange"),

            app_commands.Choice(name="🚘 Olga - Civilian", value="CivilianSedan"),
            app_commands.Choice(name="🚘 Olga - Black", value="CivilianSedan_Black"),
            app_commands.Choice(name="🚘 Olga - Wine", value="CivilianSedan_Wine"),

            app_commands.Choice(name="🚗 Gunter - Civilian", value="Hatchback_02"),
            app_commands.Choice(name="🚗 Gunter - Black", value="Hatchback_02_Black"),
            app_commands.Choice(name="🚗 Gunter - Blue", value="Hatchback_02_Blue"),

            app_commands.Choice(name="🚙 Humvee", value="Offroad_02"),

            app_commands.Choice(name="🚙 ADA 4x4 - Green", value="OffroadHatchback"),
            app_commands.Choice(name="🚙 ADA 4x4 - Blue", value="OffroadHatchback_Blue"),
            app_commands.Choice(name="🚙 ADA 4x4 - White", value="OffroadHatchback_White"),

            app_commands.Choice(name="🚚 Cargo Truck - Covered", value="Truck_01_Covered"),
            app_commands.Choice(name="🚚 Cargo Truck - Blue", value="Truck_01_Covered_Blue"),
            app_commands.Choice(name="🚚 Cargo Truck - Orange", value="Truck_01_Covered_Orange"),
        ]
    )
    async def vehicle(
        self,
        interaction: discord.Interaction,
        name: str,
        vehicle: app_commands.Choice[str],
        x: str,
        z: str
    ):
        """
        Generate DayZ vehicle event and spawn position XML.
        """

        await interaction.response.defer(ephemeral=True)

        # Progress message
        progress_msg = await interaction.followup.send(
            "⚙️ Generating vehicle XML configuration, please wait...",
            ephemeral=True
        )

        # Clean name
        clean_name = name.strip().replace(" ", "")

        # Make sure the name doesn't already contain Vehicle
        if clean_name.lower().startswith("vehicle"):
            clean_name = clean_name[7:]

        if not clean_name:
            await progress_msg.edit(
                content="❌ **Invalid vehicle name.** Please provide a name such as `Taco`."
            )
            return

        # Final DayZ event name
        event_name = f"Vehicle{clean_name}"

        # Clean coordinates
        x = x.strip()
        z = z.strip()

        # Validate coordinates
        try:
            float(x)
            float(z)
        except ValueError:
            await progress_msg.edit(
                content=(
                    "❌ **Invalid coordinate format.**\n\n"
                    "X and Z must be valid numbers.\n\n"
                    "Example:\n"
                    "`X: 2912.536377`\n"
                    "`Z: 3969.390625`"
                )
            )
            return

        vehicle_class = vehicle.value

        # --------------------------------------------------
        # EVENTS.XML
        # --------------------------------------------------

        event_xml = f"""<event name="{event_name}">
    <nominal>1</nominal>
    <min>1</min>
    <max>1</max>
    <lifetime>3888000</lifetime>
    <restock>0</restock>
    <saferadius>1</saferadius>
    <distanceradius>1</distanceradius>
    <cleanupradius>100</cleanupradius>
    <flags deletable="0" init_random="0" remove_damaged="1"/>
    <position>fixed</position>
    <limit>child</limit>
    <active>1</active>
    <children>
        <child lootmax="0" lootmin="0" max="1" min="1" type="{vehicle_class}"/>
    </children>
</event>"""

        # --------------------------------------------------
        # CFG EVENT SPAWNS
        # --------------------------------------------------

        position_xml = f"""<event name="{event_name}">
    <pos x="{x}" z="{z}" a="0.0"/>
</event>"""

        # Small UX delay
        await asyncio.sleep(1.2)

        # --------------------------------------------------
        # COPY/PASTE SECTIONS
        # --------------------------------------------------

        events_copy = (
            "```xml\n"
            f"{event_xml}\n"
            "```"
        )

        spawns_copy = (
            "```xml\n"
            f"{position_xml}\n"
            "```"
        )

        # --------------------------------------------------
        # FINAL RESPONSE
        # --------------------------------------------------

        await progress_msg.edit(
            content=(
                f"✅ **Vehicle XML Generated Successfully!**\n\n"
                f"🚗 **Vehicle:** `{vehicle_class}`\n"
                f"📛 **Event Name:** `{event_name}`\n"
                f"📍 **X:** `{x}`\n"
                f"📍 **Z:** `{z}`\n\n"
                f"**📋 Add to `events.xml`:**\n"
                f"{events_copy}\n\n"
                f"**📋 Add to `cfgeventspawns.xml`:**\n"
                f"{spawns_copy}"
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Vehicle(bot))
