import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Simulated storage (replace with real database if needed)
server_vars = {}

# Common flags
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

    # Lowercase message for easier matching
    msg_lower = message.lower()

    for key, data in map_data.items():
        if key in msg_lower:
            # Set variables
            prefix = f"{key}_"
            for flag in flags:
                server_vars[prefix + flag] = "✅"
            server_vars[key] = data['name']

            # Build embed
            embed = discord.Embed(
                title="__SETUP COMPLETE__",
                description=f"**{data['name']}’s** system is now online ✅.",
                color=0x00FF00
            )
            embed.set_image(url=data['image'])
            embed.set_author(name="🚨Setup Notification🚨")
            embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
            embed.timestamp = ctx.message.created_at

            await ctx.send(embed=embed)
            return

    await ctx.send("❌ No valid map found in your message (livonia, chernarus, sakhal).")

# Handle missing admin permission
@setup.error
async def setup_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("This command is for admins ONLY!")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
