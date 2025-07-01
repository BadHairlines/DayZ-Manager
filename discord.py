import os

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx, *, message: str):
    # Map data (expandable)
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

    # Ensure a dictionary exists for this server
    if guild_id not in server_vars:
        server_vars[guild_id] = {}

    # Try to detect which map is mentioned in the message
    matched_map_key = next((k for k in map_data if k in msg_lower), None)

    if matched_map_key:
        map_info = map_data[matched_map_key]
        prefix = f"{matched_map_key}_"

        # Set flag variables for this server and map
        for flag in flags:
            server_vars[guild_id][prefix + flag] = "✅"
        server_vars[guild_id][matched_map_key] = map_info['name']

        # Build and send confirmation embed
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

import os

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)

