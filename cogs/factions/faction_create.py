import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs import utils  # ✅ Shared DB, flag, and logging functions
from .faction_utils import ensure_faction_table, make_embed


# ==============================
# 🌍 Map Choices
# ==============================
MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]

# 🎨 Color Choices
COLOR_CHOICES = [
    app_commands.Choice(name="Red ❤️", value="#FF0000"),
    app_commands.Choice(name="Orange 🧡", value="#FFA500"),
    app_commands.Choice(name="Yellow 💛", value="#FFFF00"),
    app_commands.Choice(name="Green 💚", value="#00FF00"),
    app_commands.Choice(name="Blue 💙", value="#0000FF"),
    app_commands.Choice(name="Purple 💜", value="#800080"),
    app_commands.Choice(name="Pink 💖", value="#FF69B4"),
    app_commands.Choice(name="Cyan 💎", value="#00FFFF"),
    app_commands.Choice(name="White 🤍", value="#FFFFFF"),
    app_commands.Choice(name="Black 🖤", value="#000000"),
    app_commands.Choice(name="Grey ⚙️", value="#808080"),
    app_commands.Choice(name="Brown 🤎", value="#8B4513"),
]


class FactionCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ✅ Autocomplete for flags
    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Show a dropdown of official flags as user types."""
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in utils.FLAGS
            if current.lower() in flag.lower()
        ][:25]  # Discord max = 25 options

    # ============================================
    # 🏗️ /create-faction
    # ============================================
    @app_commands.command(
        name="create-faction",
        description="Create a faction, assign a flag, and set up its role and HQ."
    )
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)  # 👈 New autocomplete hook
    @app_commands.describe(
        name="Name of the faction",
        map="Select which map this faction belongs to",
        flag="Select the flag this faction will claim",
        color="Choose the faction color",
        leader="Select the faction leader",
        member1="Faction member #1 (optional)",
        member2="Faction member #2 (optional)",
        member3="Faction member #3 (optional)"
    )
    async def create_faction(
        self,
        interaction: discord.Interaction,
        name: str,
        map: app_commands.Choice[str],
        flag: str,
        color: app_commands.Choice[str],
        leader: discord.Member,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
    ):
        await interaction.response.defer(thinking=True)

        # 🔒 Permission Check
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Only admins can create factions.", ephemeral=True)

        # 🧩 Ensure DB ready
        if utils.db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = map.value
        role_color = discord.Color(int(color.value.strip("#"), 16))

        # 🔍 Prevent duplicates
        async with utils.db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                guild_id, name
            )
        if existing:
            return await interaction.followup.send(
                f"⚠️ Faction **{name}** already exists on {existing['map']}!",
                ephemeral=True
            )

        # 🏳️ Check Flag availability
        flags = await utils.get_all_flags(guild_id, map_key)
        flag_data = next((f for f in flags if f["flag"].lower() == flag.lower()), None)

        if not flag_data:
            return await interaction.followup.send(f"🚫 Flag `{flag}` does not exist on `{map_key}`.", ephemeral=True)

        if flag_data["status"] == "❌":
            current_owner = flag_data["role_id"]
            return await interaction.followup.send(
                f"⚠️ Flag `{flag}` is already owned by <@&{current_owner}>.",
                ephemeral=True
            )

        # ... (rest of your function remains identical)
        # 🗂️ Create role + channel, add members, save to DB, log, send embeds, etc.
