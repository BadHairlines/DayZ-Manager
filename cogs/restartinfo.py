import discord
from discord import app_commands
from datetime import datetime, timezone

class RestartInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="restartinfo", description="Shows the last and next DayZ server restarts.")
    async def restartinfo(self, interaction: discord.Interaction):

        now = datetime.now(timezone.utc)
        hour = now.hour
        minute = now.minute
        second = now.second
        now_ts = int(now.timestamp())

        quarter_hour = hour / 4
        quarter_hour_floor = int(quarter_hour)
        last_restart_hour = (quarter_hour_floor + 1) * 4

        if last_restart_hour == 24:
            last_restart_hour = 0

        seconds_since_midnight = hour * 3600 + minute * 60 + second
        last_restart_unix = now_ts + ((last_restart_hour * 3600) - seconds_since_midnight)
        next_restart_unix = last_restart_unix + 14400  # 4 hours

        msg = (
            f"⏰ **__Last Restart__:** <t:{int(last_restart_unix)}:t> - "
            f"(<t:{int(last_restart_unix)}:R>)\n"
            f"⏰ **__Next Restart__:** <t:{int(next_restart_unix)}:t> - "
            f"(<t:{int(next_restart_unix)}:R>)"
        )

        await interaction.response.send_message(msg)


async def setup(bot):
    await bot.add_cog(RestartInfo(bot))
