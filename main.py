import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from asyncio import Lock

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Thread-safe lock for JSON access
data_lock = Lock()
DATA_FILE = "server_vars.json"

# Load server vars from file
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

# Save server vars to file
async def save_data():
    async with data_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(server_vars, f, indent=4)

server_vars = load_data()

flags = [
    "Altis", "APA", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals", "CDF",
    "CHEL", "Chedaki", "Chernarus", "CMC", "Crook", "DayZ", "HunterZ", "NAPA",
    "Livonia", "LivoniaArmy", "LivoniaPolice", "NSahrani", "Pirates", "Rex",
    "Refuge", "Rooster", "RSTA", "Snake", "SSahrani", "TEC", "UEC", "Wolf",
    "Zagorky", "Zenit"
]

map_data = {
    'livonia': {
        'name': 'Livonia',
        'image': 'https://i.postimg.cc/QN9vfr9m/Livonia.jpg'
    },
    'chernarus': {
        'name': 'Chernarus',
        'image': 'https://i.postimg.cc/3RWzMsLK/Chernarus.jpg'
    },
    'sakhal': {
        'name': 'Sakhal',
        'image': 'https://i.postimg.cc/HkBSpS8j/Sakhal.png'
    }
}

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

map_choices = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]

@tree.command(name="setup", description="Setup the DayZ map system")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(selected_map="Select the map to setup")
@app_commands.choices(selected_map=map_choices)
async def setup(interaction: discord.Interaction, selected_map: app_commands.Choice[str]):
    selected_key = selected_map.value
    map_info = map_data[selected_key]
    guild_id = str(interaction.guild.id)

    if guild_id not in server_vars:
        server_vars[guild_id] = {}

    prefix = f"{selected_key}_"
    # Set all flags to ✅ for the selected map
    for flag in flags:
        server_vars[guild_id][prefix + flag] = "✅"
    # Set the main map name var
    server_vars[guild_id][selected_key] = map_info['name']

    await save_data()  # persist changes

    embed = discord.Embed(
        title="__SETUP COMPLETE__",
        description=f"**{map_info['name']}** system is now online ✅.",
        color=0x00FF00
    )
    embed.set_image(url=map_info['image'])
    embed.set_author(name="🚨 Setup Notification 🚨")
    embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    embed.timestamp = interaction.created_at

    await interaction.response.send_message(embed=embed)

@setup.error
async def setup_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("🚫 This command is for admins ONLY!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ An unexpected error occurred:\n```{error}```", ephemeral=True)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN not set in Railway environment variables.")

bot.run(TOKEN)
