import discord
from discord.ext import commands
import os

# Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Simulated per-server storage
server_vars = {}

# Your flags
flags = [
    "Altis", "APA", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals", "CDF",
    "CHEL", "Chedaki", "Chernarus", "CMC", "Crook", "DayZ", "HunterZ", "NAPA",
    "Livonia", "LivoniaArmy", "LivoniaPolice", "NSahrani", "Pirates", "Rex",
    "Refuge", "Rooster", "RSTA", "Snake", "SSahrani", "TEC", "UEC", "Wolf",
    "Zagorky", "Zenit"
]

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx, *, message: str):
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

    msg_lower = message.lower()
    guild_id = ctx.guild.id

    if guild_id not in server_vars:
        server_vars[guild_id] = {}

    matched_map_key = next((k for k in map_data if k in msg_lower), None)

    if matched_map_key:
        map_info = map_data[matched_map_key]
        prefix = f"{matched_map_key}_"

        for flag in flags:
            server_vars[guild_id][prefix + flag] = "✅"
        server_vars[guild_id][matched_map_key] = map_info['name']

        embed = discord.Embed(
            title="__SETUP COMPLETE__",
            description=f"**{map_info['name']}’s** system is now online ✅.",
            color=0x00FF00
        )
        embed.set_image(url=map_info['image'])
        embed.set_author(name="🚨 Setup Notification 🚨")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = ctx.message.created_at

        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ No valid map found in your message (livonia, chernarus, sakhal).")

# Handle missing admin permission
@setup.error
async def setup_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 This command is for admins ONLY!")

# Run the bot using Railway's environment variable
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN not set in Railway environment variables.")
bot.run(TOKEN)
