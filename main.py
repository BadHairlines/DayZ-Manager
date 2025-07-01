import discord
from discord.ext import commands
from discord import app_commands
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

server_vars = {}

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
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

# Define choices for the map option
map_choices = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]

@tree.command(name="setup", description="Setup the DayZ map system")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(map="Select the map to setup")
@app_commands.choices(map=map_choices)
async def setup(interaction: discord.Interaction, map: app_commands.Choice[str]):
    selected_key = map.value  # "livonia", "chernarus", or "sakhal"
    map_info = map_data[selected_key]
    guild_id = interaction.guild.id

    if guild_id not in server_vars:
        server_vars[guild_id] = {}

    prefix = f"{selected_key}_"
    for flag in flags:
        server_vars[guild_id][prefix + flag] = "✅"
    server_vars[guild_id][selected_key] = map_info['name']

    embed = discord.Embed(
        title="__SETUP COMPLETE__",
        description=f"**{map_info['name']}’s** system is now online ✅.",
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
        raise error

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN not set in Railway environment variables.")

bot.run(TOKEN)
