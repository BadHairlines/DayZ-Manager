import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+

class RestartInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="restartinfo",
        description="Shows the last and next DayZ server restarts (8 PM EST then every 2 hours)."
    )
    async def restartinfo(self, interaction: discord.Interaction):

        # Current time in UTC
        now_utc = datetime.now(timezone.utc)

        # Convert to Eastern time (handles EST/EDT automatically)
        eastern = ZoneInfo("America/New_York")
        now_local = now_utc.astimezone(eastern)

        # Local midnight (start of the current day in Eastern)
        local_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

        # First restart of "today" is 8 PM local time
        first_restart_today = local_midnight.replace(hour=20)  # 20:00 = 8 PM

        # Baseline: the most recent 8 PM (today or yesterday)
        if now_local >= first_restart_today:
            baseline = first_restart_today
        else:
            baseline = first_restart_today - timedelta(days=1)

        # CHANGE: 2-hour interval instead of 4 hours
        interval = timedelta(hours=2)

        # How many 2h intervals since that baseline?
        elapsed = now_local - baseline
        intervals_since = elapsed // interval  # floor division for timedeltas

        # Last & next restart in LOCAL (Eastern) time
        last_restart_local = baseline + intervals_since * interval
        next_restart_local = last_restart_local + interval

        # Convert to UTC for Discord timestamps
        last_restart_utc = last_restart_local.astimezone(timezone.utc)
        next_restart_utc = next_restart_local.astimezone(timezone.utc)

        last_restart_unix = int(last_restart_utc.timestamp())
        next_restart_unix = int(next_restart_utc.timestamp())

        msg = (
            f"⏰ **__Last Restart__:** <t:{last_restart_unix}:t> - "
            f"(<t:{last_restart_unix}:R>)\n"
            f"⏰ **__Next Restart__:** <t:{next_restart_unix}:t> - "
            f"(<t:{next_restart_unix}:R>)"
        )

        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(RestartInfo(bot))
