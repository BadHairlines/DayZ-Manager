@app_commands.command(
    name="dashboard",
    description="Post the Floors DayZ dashboard panel."
)
async def dashboard(self, interaction: discord.Interaction):

    embed = discord.Embed(
        title="🌐 Floors DayZ Dashboard",
        description=(
            "Everything is controlled through the website — no confusing commands or bots.\n\n"
            "💻 Auto Shop, Bank Accounts, Player Stats, Killfeeds, Loadouts, and more are ALL managed on the website.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "**📌 How to Get Started:**\n"
            "1. Open the dashboard using the button below\n"
            "2. If you see 'Add To Discord' — do NOT click it\n"
            "3. Click the 3 lines (menu) top right\n"
            "4. Log Into Discord\n"
            "5. Select our Discord\n"
            "6. Link your Gamertag\n"
            "7. Done — dashboard unlocks instantly"
        ),
        color=14207502
    )

    embed.set_footer(
        text="Floors DayZ • Control Panel",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )

    embed.timestamp = discord.utils.utcnow()

    view = discord.ui.View()

    view.add_item(
        discord.ui.Button(
            label="🌐 Open Dashboard",
            url="https://floorsdayz.xyz/",
            style=discord.ButtonStyle.link
        )
    )

    view.add_item(
        discord.ui.Button(
            label="📘 Docs",
            url="https://floorsdayz.xyz/docs",
            style=discord.ButtonStyle.link
        )
    )

    # IMPORTANT: stop interaction response and send normal message
    await interaction.response.defer()

    await interaction.channel.send(
        embed=embed,
        view=view
    )
