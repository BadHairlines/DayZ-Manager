import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from asyncio import Lock

# ------------------- BOT SETUP ------------------- #
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ------------------- DATA PERSISTENCE ------------------- #
DATA_FILE = "server_vars.json"
data_lock = Lock()

def load_data() -> dict:
    """Load server variables from JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

async def save_data() -> None:
    """Save server variables to JSON file safely."""
    async with data_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(server_vars, f, indent=4)

server_vars: dict = load_data()

# ------------------- CONSTANTS ------------------- #
FLAGS = [
    "Altis", "APA", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals", "CDF",
    "CHEL", "Chedaki", "Chernarus", "CMC", "Crook", "DayZ", "HunterZ", "NAPA",
    "Livonia", "LivoniaArmy", "LivoniaPolice", "NSahrani", "Pirates", "Rex",
    "Refuge", "Rooster", "RSTA", "Snake", "SSahrani", "TEC", "UEC", "Wolf",
    "Zagorky", "Zenit"
]

MAP_DATA = {
    "livonia": {"name": "Livonia", "image": "https://i.postimg.cc/QN9vfr9m/Livonia.jpg"},
    "chernarus": {"name": "Chernarus", "image": "https://i.postimg.cc/3RWzMsLK/Chernarus.jpg"},
    "sakhal": {"name": "Sakhal", "image": "https://i.postimg.cc/HkBSpS8j/Sakhal.png"},
}

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]

# ------------------- EVENTS ------------------- #
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

# ------------------- COMMANDS ------------------- #
@tree.command(
    name="setup",
    description="Setup the DayZ map system"
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(selected_map="Select the map to setup")
@app_commands.choices(selected_map=MAP_CHOICES)
async def setup(interaction: discord.Interaction, selected_map: app_commands.Choice[str]):
    guild_id = str(interaction.guild.id)
    selected_key = selected_map.value
    map_info = MAP_DATA[selected_key]

    # Initialize guild data if not present
    guild_data = server_vars.setdefault(guild_id, {})

    # Set all flags ✅
    prefix = f"{selected_key}_"
    for flag in FLAGS:
        guild_data[f"{prefix}{flag}"] = "✅"
    guild_data[selected_key] = map_info["name"]

    await save_data()

    embed = discord.Embed(
        title="__SETUP COMPLETE__",
        description=f"**{map_info['name']}** system is now online ✅.",
        color=0x00FF00,
        timestamp=interaction.created_at
    )
    embed.set_image(url=map_info["image"])
    embed.set_author(name="🚨 Setup Notification 🚨")
    embed.set_footer(
        text="DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )

    await interaction.response.send_message(embed=embed)

# ------------------- ERROR HANDLING ------------------- #
@setup.error
async def setup_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "🚫 This command is for admins ONLY!",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ An unexpected error occurred:\n```{error}```",
            ephemeral=True
        )

# ------------------- RUN BOT ------------------- #
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN not set in Railway environment variables.")

bot.run(TOKEN)
