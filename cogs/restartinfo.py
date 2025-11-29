import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta

class RestartInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="restartinfo", description="Shows the last and next DayZ server restarts.")
    async def restartinfo(self, interaction: discord.Interaction):

        # Current UTC time (Discord timestamps assume UTC)
        now = datetime.now(timezone.utc)

        # Midnight today (UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Seconds since midnight
        seconds_since_midnight = int((now - midnight).total_seconds())

        # Restart interval: 4 hours
        interval = 4 * 60 * 60  # 14400 seconds

        # Last restart = floor to nearest 4h block behind us
        last_restart_seconds = (seconds_since_midnight // interval) * interval

        # Next restart = last + 4h
        next_restart_seconds = last_restart_seconds + interval

        # Build actual datetimes
        last_restart_dt = midnight + timedelta(seconds=last_restart_seconds)
        next_restart_dt = midnight + timedelta(seconds=next_restart_seconds)

        # Convert to UNIX timestamps
        last_restart_unix = int(last_restart_dt.timestamp())
        next_restart_unix = int(next_restart_dt.timestamp())

        msg = (
            f"⏰ **__Last Restart__:** <t:{last_restart_unix}:t> - "
            f"(<t:{last_restart_unix}:R>)\n"
            f"⏰ **__Next Restart__:** <t:{next_restart_unix}:t> - "
            f"(<t:{next_restart_unix}:R>)"
        )

        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(RestartInfo(bot))
