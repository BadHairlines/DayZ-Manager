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

        # Build embed
        embed = discord.Embed(
            title="🌐 Floors DayZ Dashboard",
            description="Manage your server, track stats, and control everything in one place.\n\nClick the button below to open the dashboard.",
            color=14207502
        )

        embed.set_footer(
            text="Floors DayZ • Control Panel",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        embed.timestamp = discord.utils.utcnow()

        # Create button
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

        # Send message
        await interaction.response.send_message(
            embed=embed,
            view=view
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(dashboard(bot))
