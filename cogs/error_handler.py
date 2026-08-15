import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands


log = logging.getLogger("dayz-manager")


class ErrorHandler(commands.Cog):
    """
    Global error handler for slash and prefix commands.
    """

    def __init__(
        self,
        bot: commands.Bot
    ):
        self.bot = bot

    # =========================================================
    # ERROR RESPONSE
    # =========================================================

    async def send_error(
        self,
        send_func,
        *,
        title: str,
        desc: str,
        color: int,
    ):

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
        )

        embed.set_footer(
            text="DayZ Manager • Error Handler",
            icon_url=(
                "https://i.postimg.cc/"
                "rmXpLFpv/ewn60cg6.png"
            ),
        )

        embed.timestamp = discord.utils.utcnow()

        try:

            await send_func(
                embed=embed,
                ephemeral=True,
            )

        except TypeError:

            # Prefix commands do not support ephemeral.
            try:
                await send_func(
                    embed=embed
                )
            except Exception:
                pass

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass

        except Exception:
            log.exception(
                "Failed to send error response."
            )

    # =========================================================
    # SLASH COMMAND ERRORS
    # =========================================================

    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ):

        error = getattr(
            error,
            "original",
            error,
        )

        command = getattr(
            interaction,
            "command",
            None,
        )

        command_name = getattr(
            command,
            "qualified_name",
            "unknown",
        )

        # -----------------------------------------------------
        # IGNORE PERMISSION ERRORS
        # -----------------------------------------------------

        if isinstance(
            error,
            (
                discord.Forbidden,
                app_commands.CheckFailure,
            )
        ):
            return

        # -----------------------------------------------------
        # LOG
        # -----------------------------------------------------

        log.error(
            f"[SLASH ERROR] "
            f"/{command_name}: "
            f"{type(error).__name__}: {error}"
        )

        log.error(
            traceback.format_exc()
        )

        # -----------------------------------------------------
        # SEND ERROR
        # -----------------------------------------------------

        if interaction.response.is_done():

            send = interaction.followup.send

        else:

            send = interaction.response.send_message

        await self.send_error(
            send,
            title="❌ Unexpected Error",
            desc=(
                f"Something went wrong while executing "
                f"`/{command_name}`."
            ),
            color=0xE74C3C,
        )

    # =========================================================
    # PREFIX COMMAND ERRORS
    # =========================================================

    @commands.Cog.listener()
    async def on_command_error(
        self,
        ctx: commands.Context,
        error: Exception,
    ):

        # -----------------------------------------------------
        # COMMAND-SPECIFIC ERROR HANDLER
        # -----------------------------------------------------

        command = ctx.command

        if command and command.has_error_handler():
            return

        error = getattr(
            error,
            "original",
            error,
        )

        command_name = (
            command.qualified_name
            if command
            else "unknown"
        )

        # -----------------------------------------------------
        # SILENT ERRORS
        # -----------------------------------------------------

        if isinstance(
            error,
            (
                commands.CommandNotFound,
                commands.CheckFailure,
            )
        ):
            return

        # -----------------------------------------------------
        # PERMISSION ERROR
        # -----------------------------------------------------

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await self.send_error(
                ctx.send,
                title="🚫 Permission Denied",
                desc=(
                    "You don't have permission "
                    "to use this command."
                ),
                color=0xE74C3C,
            )

        # -----------------------------------------------------
        # MISSING ARGUMENT
        # -----------------------------------------------------

        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            name = getattr(
                getattr(
                    error,
                    "param",
                    None
                ),
                "name",
                "unknown",
            )

            return await self.send_error(
                ctx.send,
                title="⚠️ Missing Argument",
                desc=(
                    f"Missing parameter: `{name}`"
                ),
                color=0xF1C40F,
            )

        # -----------------------------------------------------
        # COOLDOWN
        # -----------------------------------------------------

        if isinstance(
            error,
            commands.CommandOnCooldown
        ):

            return await self.send_error(
                ctx.send,
                title="⏳ Cooldown",
                desc=(
                    f"Try again in "
                    f"`{error.retry_after:.1f}s`."
                ),
                color=0xF39C12,
            )

        # -----------------------------------------------------
        # LOG UNEXPECTED ERROR
        # -----------------------------------------------------

        log.error(
            f"[PREFIX ERROR] "
            f"{command_name}: "
            f"{type(error).__name__}: {error}"
        )

        log.error(
            traceback.format_exc()
        )

        # -----------------------------------------------------
        # FALLBACK
        # -----------------------------------------------------

        try:

            await self.send_error(
                ctx.send,
                title="❌ Unexpected Error",
                desc=(
                    f"Error running "
                    f"`{command_name}`."
                ),
                color=0xE74C3C,
            )

        except discord.Forbidden:

            try:

                await ctx.author.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description=(
                            f"Error running "
                            f"`{command_name}`."
                        ),
                        color=0xE74C3C,
                    )
                )

            except Exception:
                pass


async def setup(
    bot: commands.Bot
):

    await bot.add_cog(
        ErrorHandler(bot)
    )
