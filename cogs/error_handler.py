import logging
import traceback
import discord
from discord.ext import commands

log = logging.getLogger("dayz-manager")


class ErrorHandler(commands.Cog):
    """Global error handler for all commands in the DayZ Manager bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._error_cooldown = {}

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle slash command (app command) errors globally."""
        error = getattr(error, "original", error)
        user = interaction.user
        cmd_name = getattr(getattr(interaction.command, "name", None), "lower", lambda: "unknown")()

        if isinstance(error, discord.Forbidden):
            log.warning(f"Missing permission for command {cmd_name} in {interaction.guild}.")
            return

        try:
            await interaction.response.send_message(
                embed=self._make_embed(
                    "❌ Unexpected Error",
                    f"Something went wrong while executing `{cmd_name}`.\n"
                    "The devs have been notified.",
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

        tb_text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        log.error(f"Slash command error in '{cmd_name}':\n{tb_text}")

        await self._post_error_log(interaction.guild, cmd_name, user, tb_text)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Handle errors for traditional prefix commands."""
        if hasattr(getattr(ctx, "command", None), "on_error"):
            return

        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return  # ignore unknown commands silently

        elif isinstance(error, commands.CheckFailure):
            return  # permission checks already handled elsewhere

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

        tb_text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        log.error(f"Command error in {ctx.command}: {tb_text}")

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
            try:
                await ctx.author.send(embed=embed)
            except Exception:
                pass

        if ctx.guild:
            await self._post_error_log(ctx.guild, cmd_name, ctx.author, tb_text)

    async def _post_error_log(self, guild: discord.Guild, cmd_name: str, user, tb_text: str):
        """Safely post a formatted traceback to a dedicated error channel."""
        if guild is None:
            return

        last_sent = self._error_cooldown.get(guild.id)
        if last_sent and (discord.utils.utcnow() - last_sent).total_seconds() < 15:
            return
        self._error_cooldown[guild.id] = discord.utils.utcnow()

        try:
            channel = discord.utils.get(guild.text_channels, name="bot-errors")
            if not channel:
                try:
                    channel = await guild.create_text_channel("bot-errors")
                except discord.Forbidden:
                    return

            trimmed_tb = tb_text[:1900]
            embed = discord.Embed(
                title="💥 Bot Exception Caught",
                description=(
                    f"**Command:** `{cmd_name}`\n"
                    f"**User:** {getattr(user, 'mention', 'N/A')}\n\n"
                    f"```py\n{trimmed_tb}```"
                ),
                color=0xE74C3C,
            )
            embed.timestamp = discord.utils.utcnow()
            embed.set_footer(text=f"DayZ Manager • {guild.name}")

            await channel.send(embed=embed)
        except Exception as e:
            log.warning(f"Failed to post error log to {guild.name}: {e}")

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
