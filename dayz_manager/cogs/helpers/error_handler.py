import discord
from discord.ext import commands
import traceback

class ErrorHandler(commands.Cog):
    """Global error handler for all commands in the DayZ Manager bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=self._make_embed("🚫 Permission Denied", "You don't have permission to use this command.", 0xE74C3C), delete_after=10)
            return

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=self._make_embed("⚠️ Missing Argument", f"You're missing a required parameter: `{error.param.name}`", 0xF1C40F), delete_after=10)
            return

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=self._make_embed("⏳ Slow down!", f"This command is on cooldown. Try again in {error.retry_after:.1f}s.", 0xF39C12), delete_after=10)
            return

        else:
            print("".join(traceback.format_exception(type(error), error, error.__traceback__)))

            embed = self._make_embed("❌ Unexpected Error", f"An unexpected error occurred while running `{ctx.command}`.\nThe devs have been notified.", 0xE74C3C)
            await ctx.send(embed=embed, delete_after=15)

            error_channel = discord.utils.get(ctx.guild.text_channels, name="bot-errors")
            if error_channel is None:
                try:
                    error_channel = await ctx.guild.create_text_channel("bot-errors")
                except discord.Forbidden:
                    return

            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            await error_channel.send(embed=discord.Embed(
                title="💥 Bot Exception Caught",
                description=f"**Command:** `{ctx.command}`\n**User:** {ctx.author.mention}\n**Channel:** {ctx.channel.mention}\n\n```py\n{tb[:1900]}```",
                color=0xE74C3C
            ))

    def _make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(text="DayZ Manager • Error Handler", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
