import logging
import traceback
import discord
from discord.ext import commands

log = logging.getLogger("dayz-manager")


class ErrorHandler(commands.Cog):
    """Global error handler for all commands in the bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- EMBED ----------------

    def _make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(
            text="DayZ Manager • Error Handler",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png",
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    # ---------------- SLASH ERRORS ----------------

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        error = getattr(error, "original", error)

        cmd_name = (
            getattr(getattr(interaction, "command", None), "name", None)
            or "unknown"
        )

        # ignore permissions silently
        if isinstance(error, discord.Forbidden):
            return

        # log everything (IMPORTANT — your version didn't actually surface errors)
        log.error(f"[SLASH ERROR] /{cmd_name}: {error}")
        log.error(traceback.format_exc())

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=self._make_embed(
                        "❌ Unexpected Error",
                        f"Something went wrong while executing `/{cmd_name}`.",
                        0xE74C3C,
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=self._make_embed(
                        "❌ Unexpected Error",
                        f"Something went wrong while executing `/{cmd_name}`.",
                        0xE74C3C,
                    ),
                    ephemeral=True,
                )

        except Exception:
            pass

    # ---------------- PREFIX ERRORS ----------------

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        if hasattr(getattr(ctx, "command", None), "on_error"):
            return

        error = getattr(error, "original", error)

        # ignore non-critical errors
        if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
            return

        cmd_name = getattr(getattr(ctx, "command", None), "qualified_name", "unknown")

        # permissions
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

        # missing args
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

        # cooldown
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                embed=self._make_embed(
                    "⏳ Cooldown",
                    f"Try again in `{error.retry_after:.1f}s`.",
                    0xF39C12,
                ),
                delete_after=10,
            )
            return

        # log unexpected errors (this was missing in your version)
        log.error(f"[PREFIX ERROR] {cmd_name}: {error}")
        log.error(traceback.format_exc())

        # fallback user message
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


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
