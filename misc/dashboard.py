import discord
from discord import app_commands
from discord.ext import commands


class dashboard(commands.Cog):
    """Dashboard / Panel Command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========= /dashboard =========
    @app_commands.command(
        name="dashboard",
        description="Post the Floors DayZ dashboard panel."
    )
    async def dashboard(self, interaction: discord.Interaction):

        file = discord.File("/mnt/data/image.png", filename="banner.png")

        embed = discord.Embed(
            title="🌐 Floors DayZ Dashboard",
            description=(
                "Everything is controlled through the website — no confusing commands or bots.\n\n"
                
                "💻 Auto Shop, Bank Accounts, Player Stats, Killfeeds, Loadouts, and more are ALL managed on the website.\n"
                "Think HulksKillfeed / DayZ++ style systems — fully modernized into one central dashboard.\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━\n"
                "**📌 How to Get Started:**\n"
                "1. Open the dashboard using the button below\n"
                "2. If you see 'Add To Discord' — do NOT click it\n"
                "3. Click the 3 lines (menu icon) in the top right\n"
                "4. Select 'Log Into Discord'\n"
                "5. Choose our Discord server when prompted\n"
                "6. Link your Gamertag\n"
                "7. Once complete, your full dashboard unlocks instantly\n\n"
                
                "After that, you’ll be able to view and manage everything directly from the website."
            ),
            color=14207502
        )

        # 🔥 THIS is what shows your image at the top of the embed
        embed.set_image(url="attachment://banner.png")

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

        # IMPORTANT: send as normal message (not interaction style)
        await interaction.response.defer()

        await interaction.channel.send(
            embed=embed,
            view=view,
            file=file
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(dashboard(bot))
