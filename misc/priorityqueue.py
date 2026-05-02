import discord
from discord import app_commands
from discord.ext import commands


class priorityqueue(commands.Cog):
    """Priority Queue Panel Command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========= /priorityqueue =========
    @app_commands.command(
        name="priorityqueue",
        description="Post the Priority Queue access panel."
    )
    async def priorityqueue(self, interaction: discord.Interaction):

        # Build embed
        embed = discord.Embed(
            title="⚡ HIVE PRIORITY QUEUE ACCESS",
            description=(
                "Secure your spot before server wipes or full queues hit.\n"
                "Priority Queue gives you **fast-track access** into the server.\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n"
                "**🎯 What Priority Queue Includes:**\n"
                "• Instant or boosted server entry\n"
                "• Bypass full queue delays\n"
                "• Reserved login priority slot\n"
                "• Faster rejoin after crashes or kicks\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n"
                "**📌 How to Activate Priority:**\n"
                "1. Click the button below to open the store\n"
                "2. Purchase your Priority Queue slot\n"
                "3. Link your Gamertag if prompted\n"
                "4. Restart your game if you're already in queue\n"
                "5. Join the server and you’ll be placed ahead of standard players\n\n"

                "💡 *Note: Priority is account-linked — not transferable between users.*"
            ),
            color=0xF5C542  # hive gold color
        )

        embed.set_footer(text="Hive Priority System • Faster Access • Less Waiting")
        embed.timestamp = discord.utils.utcnow()

        # Buttons
        view = discord.ui.View()

        view.add_item(
            discord.ui.Button(
                label="⚡ Get Priority Access",
                url="https://floorsdayz.xyz/",
                style=discord.ButtonStyle.link
            )
        )

        await interaction.response.defer()

        await interaction.channel.send(
            embed=embed,
            view=view
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(priorityqueue(bot))
