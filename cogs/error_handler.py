import discord
from discord.ext import commands
import traceback

class ErrorHandler(commands.Cog):
    """Global error handler for all commands in the DayZ Manager bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        # Skip if the command implements its own handler
        if hasattr(getattr(ctx, "command", None), "on_error"):
            return

        # Unwrap the original error
        error = getattr(error, "original", error)

        # Common, user-friendly errors
        if isinstance(error, commands.CommandNotFound):
            return  # silently ignore unknown prefix commands

        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=self._make_embed(
                    "🚫 Permission Denied",
                    "You don't have permission to use this command.",
                    0xE74C3C,
                ),
                delete_after=10,
            )
            return

        elif isinstance(error, commands.MissingRequiredArgument):
            missing = getattr(error, "param", None)
            name = getattr(missing, "name", "unknown")
            await ctx.send(
                embed=self._make_embed(
                    "⚠️ Missing Argument",
                    f"You're missing a required parameter: `{name}`",
                    0xF1C40F,
                ),
                delete_after=10,
            )
            return

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                embed=self._make_embed(
                    "⏳ Slow down!",
                    f"This command is on cooldown. Try again in {error.retry_after:.1f}s.",
                    0xF39C12,
                ),
                delete_after=10,
            )
            return

        # Unexpected errors
        # Log full traceback to console
        tb_text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        print(tb_text)

        # Let the user know something went wrong
        cmd_name = getattr(getattr(ctx, "command", None), "qualified_name", "unknown")
        embed = self._make_embed(
            "❌ Unexpected Error",
            f"An unexpected error occurred while running `{cmd_name}`.\n"
            f"The devs have been notified.",
            0xE74C3C,
        )
        try:
            await ctx.send(embed=embed, delete_after=15)
        except discord.Forbidden:
            pass  # can't send here

        # DM or guild-less context? Stop here.
        if ctx.guild is None:
            return

        # Try to report detailed error in a dedicated channel
        try:
            error_channel = discord.utils.get(ctx.guild.text_channels, name="bot-errors")
            if error_channel is None:
                try:
                    error_channel = await ctx.guild.create_text_channel("bot-errors")
                except discord.Forbidden:
                    return  # no perms to create

            trimmed_tb = tb_text[:1900]  # keep under embed limit
            await error_channel.send(
                embed=discord.Embed(
                    title="💥 Bot Exception Caught",
                    description=(
                        f"**Command:** `{cmd_name}`\n"
                        f"**User:** {ctx.author.mention}\n"
                        f"**Channel:** {getattr(ctx.channel, 'mention', 'N/A')}\n\n"
                        f"```py\n{trimmed_tb}```"
                    ),
                    color=0xE74C3C,
                )
            )
        except Exception:
            # Avoid cascading error loops
            pass

    def _make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(
            text="DayZ Manager • Error Handler",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png",
        )
        embed.timestamp = discord.utils.utcnow()
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
