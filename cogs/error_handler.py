import traceback
import discord
from discord.ext import commands


class ErrorHandler(commands.Cog):
    """Global error handler for all commands in the bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle slash command errors globally."""

        error = getattr(error, "original", error)

        cmd_name = getattr(getattr(interaction.command, "name", None), "lower", lambda: "unknown")()

        if isinstance(error, discord.Forbidden):
            return

        try:
            await interaction.response.send_message(
                embed=self._make_embed(
                    "❌ Unexpected Error",
                    f"Something went wrong while executing `{cmd_name}`.",
                    0xE74C3C,
                ),
                ephemeral=True
            )

        except discord.InteractionResponded:
            await interaction.followup.send(
                "❌ Something went wrong while running this command.",
                ephemeral=True
            )

        except Exception:
            pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Handle prefix command errors globally."""

        if hasattr(getattr(ctx, "command", None), "on_error"):
            return

        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=self._make_embed(
                    "🚫 Permission Denied",
                    "You don't have permission to use this command.",
                    0xE74C3C,
                ),
                delete_after=10,
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            name = getattr(getattr(error, "param", None), "name", "unknown")

            await ctx.send(
                embed=self._make_embed(
                    "⚠️ Missing Argument",
                    f"Missing parameter: `{name}`",
                    0xF1C40F,
                ),
                delete_after=10,
            )
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                embed=self._make_embed(
                    "⏳ Cooldown",
                    f"Try again in {error.retry_after:.1f}s.",
                    0xF39C12,
                ),
                delete_after=10,
            )
            return

        # generic fallback (no logging, just silent + user message)
        cmd_name = getattr(getattr(ctx, "command", None), "qualified_name", "unknown")

        try:
            await ctx.send(
                embed=self._make_embed(
                    "❌ Unexpected Error",
                    f"Error running `{cmd_name}`.",
                    0xE74C3C,
                ),
                delete_after=15,
            )
        except discord.Forbidden:
            try:
                await ctx.author.send(
                    embed=self._make_embed(
                        "❌ Error",
                        f"Error running `{cmd_name}`.",
                        0xE74C3C,
                    )
                )
            except Exception:
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
