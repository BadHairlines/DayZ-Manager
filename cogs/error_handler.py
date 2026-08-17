from __future__ import annotations

import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("dayz-manager")


class ErrorHandler(commands.Cog):
    """Centralized, user-friendly error handling."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_error(
        self,
        send_func,
        title: str,
        description: str,
        color: int = 0xE74C3C,
    ) -> None:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        embed.set_footer(text="DayZ Manager • Error Handler")
        embed.timestamp = discord.utils.utcnow()

        try:
            await send_func(embed=embed, ephemeral=True)
        except TypeError:
            try:
                await send_func(embed=embed)
            except Exception:
                pass
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        original = getattr(error, "original", error)

        command = interaction.command
        name = command.qualified_name if command else "unknown"

        if isinstance(original, app_commands.CheckFailure):
            message = str(original) or "You do not have permission to use this command."

            if interaction.response.is_done():
                await self.send_error(
                    interaction.followup.send,
                    "🚫 Permission Denied",
                    message,
                )
            else:
                await self.send_error(
                    interaction.response.send_message,
                    "🚫 Permission Denied",
                    message,
                )
            return

        if isinstance(original, app_commands.CommandOnCooldown):
            await self.send_error(
                interaction.followup.send
                if interaction.response.is_done()
                else interaction.response.send_message,
                "⏳ Cooldown",
                f"Please try again in `{original.retry_after:.1f}s`.",
                0xF39C12,
            )
            return

        log.error(
            "Unhandled slash error in /%s: %s: %s",
            name,
            type(original).__name__,
            original,
        )
        log.error(traceback.format_exc())

        send = (
            interaction.followup.send
            if interaction.response.is_done()
            else interaction.response.send_message
        )

        await self.send_error(
            send,
            "❌ Unexpected Error",
            f"Something went wrong while running `/{name}`.\n"
            "The error has been logged for staff.",
        )

    @commands.Cog.listener()
    async def on_command_error(
        self,
        ctx: commands.Context,
        error: Exception,
    ) -> None:
        if ctx.command and ctx.command.has_error_handler():
            return

        original = getattr(error, "original", error)

        if isinstance(
            original,
            (commands.CommandNotFound, commands.CheckFailure),
        ):
            return

        if isinstance(original, commands.MissingPermissions):
            return await self.send_error(
                ctx.send,
                "🚫 Permission Denied",
                "You don't have permission to use this command.",
            )

        if isinstance(original, commands.MissingRequiredArgument):
            return await self.send_error(
                ctx.send,
                "⚠️ Missing Argument",
                f"Missing parameter: `{original.param.name}`.",
                0xF1C40F,
            )

        if isinstance(original, commands.CommandOnCooldown):
            return await self.send_error(
                ctx.send,
                "⏳ Cooldown",
                f"Try again in `{original.retry_after:.1f}s`.",
                0xF39C12,
            )

        log.error(
            "Unhandled prefix error in %s: %s: %s",
            ctx.command.qualified_name if ctx.command else "unknown",
            type(original).__name__,
            original,
        )
        log.error(traceback.format_exc())

        await self.send_error(
            ctx.send,
            "❌ Unexpected Error",
            "Something went wrong while running that command.\n"
            "The error has been logged for staff.",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
