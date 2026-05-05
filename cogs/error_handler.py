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
    # ERROR RESPONSE HELPER
    # -----------------------------
    async def send_error(self, send_func, *, title: str, desc: str, color: int):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(
            text="DayZ Manager • Error Handler",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png",
        )
        embed.timestamp = discord.utils.utcnow()

        try:
            await send_func(embed=embed, ephemeral=True)
        except TypeError:
            # fallback for ctx.send (no ephemeral support)
            await send_func(embed=embed)
        except Exception:
            pass

    # -----------------------------
    # SLASH COMMAND ERRORS
    # -----------------------------
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        error = getattr(error, "original", error)

        cmd_name = getattr(getattr(interaction, "command", None), "name", "unknown")

        # ignore permission silently (optional: you can notify instead)
        if isinstance(error, discord.Forbidden):
            return

        log.error(f"[SLASH ERROR] /{cmd_name}: {error}")
        log.error(traceback.format_exc())

        send = (
            interaction.followup.send
            if interaction.response.is_done()
            else interaction.response.send_message
        )

        await self.send_error(
            send,
            title="❌ Unexpected Error",
            desc=f"Something went wrong while executing `/{cmd_name}`.",
            color=0xE74C3C,
        )

    # -----------------------------
    # PREFIX COMMAND ERRORS
    # -----------------------------
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        # ignore per-command overrides
        if hasattr(getattr(ctx.command, "on_error", None)):
            return

        error = getattr(error, "original", error)
        cmd_name = getattr(getattr(ctx.command, "qualified_name", None), "unknown", "unknown")

        # -----------------------------
        # IGNORE SILENT ERRORS
        # -----------------------------
        if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
            return

        # -----------------------------
        # HANDLED ERRORS
        # -----------------------------
        if isinstance(error, commands.MissingPermissions):
            return await self.send_error(
                ctx.send,
                title="🚫 Permission Denied",
                desc="You don't have permission to use this command.",
                color=0xE74C3C,
            )

        if isinstance(error, commands.MissingRequiredArgument):
            name = getattr(getattr(error, "param", None), "name", "unknown")

            return await self.send_error(
                ctx.send,
                title="⚠️ Missing Argument",
                desc=f"Missing parameter: `{name}`",
                color=0xF1C40F,
            )

        if isinstance(error, commands.CommandOnCooldown):
            return await self.send_error(
                ctx.send,
                title="⏳ Cooldown",
                desc=f"Try again in `{error.retry_after:.1f}s`.",
                color=0xF39C12,
            )

        # -----------------------------
        # LOG UNEXPECTED ERRORS
        # -----------------------------
        log.error(f"[PREFIX ERROR] {cmd_name}: {error}")
        log.error(traceback.format_exc())

        # -----------------------------
        # FALLBACK RESPONSE
        # -----------------------------
        try:
            await self.send_error(
                ctx.send,
                title="❌ Unexpected Error",
                desc=f"Error running `{cmd_name}`.",
                color=0xE74C3C,
            )
        except discord.Forbidden:
            try:
                await ctx.author.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description=f"Error running `{cmd_name}`.",
                        color=0xE74C3C,
                    )
                )
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
