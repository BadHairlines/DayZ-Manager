import discord
from discord import app_commands
from discord.ext import commands

class BotInfo(commands.Cog):
    """Owner-only commands for server management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="guilds",
        description="List all servers the bot is in (owner only)."
    )
    async def guilds(self, interaction: discord.Interaction):
        # Check if the user is the bot owner
        app_info = await self.bot.application_info()
        if interaction.user.id != app_info.owner.id:
            return await interaction.response.send_message(
                "🚫 Only the bot owner can use this command.", ephemeral=True
            )

        if not self.bot.guilds:
            return await interaction.response.send_message(
                "I'm not in any servers!", ephemeral=True
            )

        lines = [f"{g.name} ({g.id}) — {g.member_count} members" for g in self.bot.guilds]

        # Split messages into chunks under 2000 characters
        chunk_size = 2000
        message = ""
        await interaction.response.defer(ephemeral=True)
        for line in lines:
            if len(message) + len(line) + 1 > chunk_size:
                await interaction.followup.send(f"```{message}```", ephemeral=True)
                message = ""
            message += line + "\n"
        if message:
            await interaction.followup.send(f"```{message}```", ephemeral=True)

async def setup(bot: commands.Bot):
    # Add the cog and register the slash command
    await bot.add_cog(BotInfo(bot))
    bot.tree.add_command(BotInfo.guilds)
