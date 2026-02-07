import discord
from discord.ext import commands

class BotInfo(commands.Cog):
    """Commands for bot owner only."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="guilds")
    @commands.is_owner()  # only you can run this
    async def guilds(self, ctx):
        """List all servers the bot is in."""
        if not self.bot.guilds:
            return await ctx.send("I'm not in any servers!")

        lines = [f"{guild.name} ({guild.id}) — {guild.member_count} members" for guild in self.bot.guilds]

        # Discord messages are limited to 2000 characters, so split if needed
        chunk_size = 2000
        message = ""
        for line in lines:
            if len(message) + len(line) + 1 > chunk_size:
                await ctx.send(f"```{message}```")
                message = ""
            message += line + "\n"
        if message:
            await ctx.send(f"```{message}```")

async def setup(bot):
    await bot.add_cog(BotInfo(bot))
