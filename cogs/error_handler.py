import logging
import traceback
import discord
from discord.ext import commands

log = logging.getLogger("dayz-manager")


class ErrorHandler(commands.Cog):
    """Global error handler for both slash + prefix commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------
    # ERROR RESPONSE HELPERS
    # -----------------------------
    async def send_error(self, target, *, title: str, desc: str, color: int):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(
            text="DayZ Manager • Error Handler",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png",
        )
        embed.timestamp = discord.utils.utcnow()

        try:
            await target(embed=embed, ephemeral=True)
        except Exception:
            pass

    # -----------------------------
    # SLASH COMMAND ERRORS
    # -----------------------------
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        error = getattr(error, "original", error)

        cmd_name = getattr(getattr(interaction, "command", None), "name", "unknown")

        if isinstance(error, discord.Forbidden):
            return

        log.error(f"[SLASH ERROR] /{cmd_name}: {error}")
        log.error(traceback.format_exc())

        response = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message

        await self.send_error(
            response,
            title="❌ Unexpected Error",
            desc=f"Something went wrong while executing `/{cmd_name}`.",
            color=0xE74C3C,
        )

    # -----------------------------
    # PREFIX COMMAND ERRORS
    # -----------------------------
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        if hasattr(getattr(ctx, "command", None), "on_error"):
            return

        error = getattr(error, "original", error)
        cmd_name = getattr(getattr(ctx, "command", None), "qualified_name", "unknown")

        # ignore harmless errors
        if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
            return

        # permission error
        if isinstance(error, commands.MissingPermissions):
            return await self.send_error(
                ctx.send,
                title="🚫 Permission Denied",
                desc="You don't have permission to use this command.",
                color=0xE74C3C,
            )

        # missing argument
        if isinstance(error, commands.MissingRequiredArgument):
            name = getattr(getattr(error, "param", None), "name", "unknown")

            return await self.send_error(
                ctx.send,
                title="⚠️ Missing Argument",
                desc=f"Missing parameter: `{name}`",
                color=0xF1C40F,
            )

        # cooldown
        if isinstance(error, commands.CommandOnCooldown):
            return await self.send_error(
                ctx.send,
                title="⏳ Cooldown",
                desc=f"Try again in `{error.retry_after:.1f}s`.",
                color=0xF39C12,
            )

        # log unexpected errors
        log.error(f"[PREFIX ERROR] {cmd_name}: {error}")
        log.error(traceback.format_exc())

        # fallback response
        try:
            await self.send_error(
                ctx.send,
                title="❌ Unexpected Error",
                desc=f"Error running `{cmd_name}`.",
                color=0xE74C3C,
            )
        except discord.Forbidden:
            try:
                await self.send_error(
                    ctx.author.send,
                    title="❌ Error",
                    desc=f"Error running `{cmd_name}`.",
                    color=0xE74C3C,
                )
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
