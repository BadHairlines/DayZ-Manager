import discord
from discord import app_commands
from discord.ext import commands

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import json
import os
import asyncio


# =========================================================
# CONFIGURATION
# =========================================================

CONFIG_FILE = "restart_configs.json"

DEFAULT_INTERVAL = 2
DEFAULT_TIME = "20:00"
DEFAULT_TIMEZONE = "America/New_York"

ALLOWED_INTERVALS = {
    2: "Every 2 Hours",
    4: "Every 4 Hours",
    6: "Every 6 Hours",
    8: "Every 8 Hours",
    12: "Every 12 Hours",
    24: "Every 24 Hours",
}


# =========================================================
# RESTART INFO COG
# =========================================================

class RestartInfo(commands.Cog):
    """
    Per-server DayZ restart schedule manager.

    Commands:
        /restartsetup
        /restartinfo
        /restartschedule
        /restartconfig
        /restartreset
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.configs = {}
        self.config_lock = asyncio.Lock()

        self.load_configs()

    # =====================================================
    # CONFIG FILE
    # =====================================================

    def load_configs(self):
        """Load restart configurations from disk."""

        if not os.path.exists(CONFIG_FILE):
            self.configs = {}
            return

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self.configs = json.load(f)

        except (json.JSONDecodeError, OSError):
            print(
                f"[RestartInfo] Failed to load {CONFIG_FILE}. "
                f"Starting with empty configuration."
            )
            self.configs = {}

    async def save_configs(self):
        """Save restart configurations to disk."""

        async with self.config_lock:
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(
                        self.configs,
                        f,
                        indent=4,
                        sort_keys=True
                    )

            except OSError as e:
                print(f"[RestartInfo] Failed to save config: {e}")

    # =====================================================
    # DEFAULT CONFIG
    # =====================================================

    def get_config(self, guild_id: int):
        """
        Get a server's restart configuration.

        If the server has never been configured, return defaults.
        """

        guild_id = str(guild_id)

        if guild_id not in self.configs:
            return {
                "interval": DEFAULT_INTERVAL,
                "restart_time": DEFAULT_TIME,
                "timezone": DEFAULT_TIMEZONE,
            }

        config = self.configs[guild_id]

        return {
            "interval": int(config.get("interval", DEFAULT_INTERVAL)),
            "restart_time": config.get("restart_time", DEFAULT_TIME),
            "timezone": config.get("timezone", DEFAULT_TIMEZONE),
        }

    # =====================================================
    # TIME PARSER
    # =====================================================

    @staticmethod
    def parse_time(time_string: str):
        """
        Accepts:

            20:00
            08:00
            8:00 PM
            8 PM
            12:30 AM

        Returns:
            (hour, minute)
        """

        value = time_string.strip().upper()

        formats = [
            "%H:%M",
            "%I:%M %p",
            "%I %p",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.hour, parsed.minute
            except ValueError:
                continue

        return None

    # =====================================================
    # TIMEZONE VALIDATION
    # =====================================================

    @staticmethod
    def get_timezone(timezone_name: str):
        """Return a ZoneInfo object or None."""

        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return None

    # =====================================================
    # CALCULATE RESTART
    # =====================================================

    def calculate_restart_times(
        self,
        config,
        count=1
    ):
        """
        Calculate the most recent restart and upcoming restarts.

        Returns:
            last_restart_local,
            upcoming_restart_list
        """

        interval_hours = config["interval"]
        restart_time = config["restart_time"]
        timezone_name = config["timezone"]

        timezone_obj = self.get_timezone(timezone_name)

        if timezone_obj is None:
            timezone_obj = ZoneInfo(DEFAULT_TIMEZONE)

        parsed = self.parse_time(restart_time)

        if parsed is None:
            parsed = (20, 0)

        restart_hour, restart_minute = parsed

        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(timezone_obj)

        # -------------------------------------------------
        # Create today's anchor restart
        # -------------------------------------------------

        anchor = now_local.replace(
            hour=restart_hour,
            minute=restart_minute,
            second=0,
            microsecond=0
        )

        # -------------------------------------------------
        # Find the most recent restart.
        #
        # We go backwards one day when necessary.
        # -------------------------------------------------

        if now_local < anchor:
            anchor -= timedelta(days=1)

        interval = timedelta(hours=interval_hours)

        elapsed = now_local - anchor

        intervals_since = elapsed // interval

        last_restart = anchor + (
            intervals_since * interval
        )

        # -------------------------------------------------
        # Build upcoming restarts
        # -------------------------------------------------

        upcoming = []

        next_restart = last_restart + interval

        for _ in range(count):
            upcoming.append(next_restart)
            next_restart += interval

        return last_restart, upcoming

    # =====================================================
    # DISCORD TIMESTAMP
    # =====================================================

    @staticmethod
    def discord_timestamp(dt: datetime, style="F"):
        """Convert datetime to a Discord timestamp."""

        utc_dt = dt.astimezone(timezone.utc)

        return f"<t:{int(utc_dt.timestamp())}:{style}>"

    # =====================================================
    # COMMAND: RESTART SETUP
    # =====================================================

    @app_commands.command(
        name="restartsetup",
        description="Configure your server's DayZ restart schedule."
    )
    @app_commands.describe(
        interval="How often the server restarts.",
        restart_time="Time of the first restart, e.g. 8:00 PM or 20:00.",
        timezone="Timezone used for the restart schedule."
    )
    @app_commands.choices(
        interval=[
            app_commands.Choice(
                name="Every 2 Hours",
                value=2
            ),
            app_commands.Choice(
                name="Every 4 Hours",
                value=4
            ),
            app_commands.Choice(
                name="Every 6 Hours",
                value=6
            ),
            app_commands.Choice(
                name="Every 8 Hours",
                value=8
            ),
            app_commands.Choice(
                name="Every 12 Hours",
                value=12
            ),
            app_commands.Choice(
                name="Every 24 Hours",
                value=24
            ),
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def restartsetup(
        self,
        interaction: discord.Interaction,
        interval: app_commands.Choice[int],
        restart_time: str,
        timezone: str = DEFAULT_TIMEZONE,
    ):
        """Configure the restart schedule for this Discord server."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # Validate time
        # -------------------------------------------------

        parsed_time = self.parse_time(restart_time)

        if parsed_time is None:
            await interaction.response.send_message(
                "❌ **Invalid restart time.**\n\n"
                "Use one of these formats:\n"
                "• `20:00`\n"
                "• `08:00`\n"
                "• `8:00 PM`\n"
                "• `8 PM`\n"
                "• `12:30 AM`",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # Validate timezone
        # -------------------------------------------------

        timezone_obj = self.get_timezone(timezone)

        if timezone_obj is None:
            await interaction.response.send_message(
                "❌ **Invalid timezone.**\n\n"
                "Examples:\n"
                "• `America/New_York`\n"
                "• `America/Chicago`\n"
                "• `America/Denver`\n"
                "• `America/Los_Angeles`\n"
                "• `UTC`",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # Normalize time
        # -------------------------------------------------

        hour, minute = parsed_time

        normalized_time = f"{hour:02d}:{minute:02d}"

        # -------------------------------------------------
        # Save configuration
        # -------------------------------------------------

        guild_id = str(interaction.guild.id)

        self.configs[guild_id] = {
            "interval": interval.value,
            "restart_time": normalized_time,
            "timezone": timezone,
        }

        await self.save_configs()

        # -------------------------------------------------
        # Calculate next restart
        # -------------------------------------------------

        config = self.get_config(interaction.guild.id)

        last_restart, upcoming = self.calculate_restart_times(
            config,
            count=1
        )

        next_restart = upcoming[0]

        embed = discord.Embed(
            title="🔄 Restart Schedule Updated",
            description=(
                f"Restart settings for **{interaction.guild.name}** "
                f"have been updated."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="⏱️ Restart Interval",
            value=ALLOWED_INTERVALS[interval.value],
            inline=True
        )

        embed.add_field(
            name="🕐 Restart Time",
            value=datetime.strptime(
                normalized_time,
                "%H:%M"
            ).strftime("%I:%M %p"),
            inline=True
        )

        embed.add_field(
            name="🌎 Timezone",
            value=f"`{timezone}`",
            inline=True
        )

        embed.add_field(
            name="⏰ Next Restart",
            value=(
                f"{self.discord_timestamp(next_restart, 'F')}\n"
                f"{self.discord_timestamp(next_restart, 'R')}"
            ),
            inline=False
        )

        embed.set_footer(
            text="Use /restartinfo to view the current restart information."
        )

        await interaction.response.send_message(embed=embed)

    # =====================================================
    # COMMAND: RESTART INFO
    # =====================================================

    @app_commands.command(
        name="restartinfo",
        description="Shows the last and next DayZ server restart."
    )
    async def restartinfo(
        self,
        interaction: discord.Interaction
    ):
        """Display the server's last and next restart."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        config = self.get_config(interaction.guild.id)

        last_restart, upcoming = self.calculate_restart_times(
            config,
            count=1
        )

        next_restart = upcoming[0]

        timezone_name = config["timezone"]
        interval = config["interval"]

        # -------------------------------------------------
        # Format configured time
        # -------------------------------------------------

        parsed = self.parse_time(config["restart_time"])

        if parsed:
            hour, minute = parsed

            formatted_time = datetime(
                2000,
                1,
                1,
                hour,
                minute
            ).strftime("%I:%M %p")
        else:
            formatted_time = config["restart_time"]

        # -------------------------------------------------
        # Build embed
        # -------------------------------------------------

        embed = discord.Embed(
            title="🔄 DayZ Server Restart",
            description=(
                f"Restart schedule for **{interaction.guild.name}**"
            ),
            color=discord.Color.orange()
        )

        embed.add_field(
            name="⏮️ Last Restart",
            value=(
                f"{self.discord_timestamp(last_restart, 'F')}\n"
                f"{self.discord_timestamp(last_restart, 'R')}"
            ),
            inline=False
        )

        embed.add_field(
            name="⏭️ Next Restart",
            value=(
                f"{self.discord_timestamp(next_restart, 'F')}\n"
                f"**{self.discord_timestamp(next_restart, 'R')}**"
            ),
            inline=False
        )

        embed.add_field(
            name="⏱️ Schedule",
            value=ALLOWED_INTERVALS.get(
                interval,
                f"Every {interval} Hours"
            ),
            inline=True
        )

        embed.add_field(
            name="🕐 Restart Time",
            value=formatted_time,
            inline=True
        )

        embed.add_field(
            name="🌎 Timezone",
            value=f"`{timezone_name}`",
            inline=True
        )

        embed.set_footer(
            text="Restart times automatically adjust for EST/EDT and Discord displays times in each user's local timezone."
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =====================================================
    # COMMAND: RESTART SCHEDULE
    # =====================================================

    @app_commands.command(
        name="restartschedule",
        description="Shows the upcoming DayZ server restart schedule."
    )
    @app_commands.describe(
        count="Number of upcoming restarts to display (1-10)."
    )
    async def restartschedule(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 10] = 5
    ):
        """Display upcoming restarts."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        config = self.get_config(interaction.guild.id)

        _, upcoming = self.calculate_restart_times(
            config,
            count=count
        )

        embed = discord.Embed(
            title="📅 Upcoming Server Restarts",
            description=(
                f"**{interaction.guild.name}**\n"
                f"Every **{config['interval']} hours**"
            ),
            color=discord.Color.blurple()
        )

        lines = []

        for index, restart in enumerate(upcoming, start=1):
            lines.append(
                f"**{index}.** "
                f"{self.discord_timestamp(restart, 'F')} "
                f"• {self.discord_timestamp(restart, 'R')}"
            )

        embed.description = (
            f"**{interaction.guild.name}**\n\n"
            + "\n".join(lines)
        )

        embed.set_footer(
            text=(
                f"Schedule: Every {config['interval']} hours • "
                f"{config['timezone']}"
            )
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =====================================================
    # COMMAND: RESTART CONFIG
    # =====================================================

    @app_commands.command(
        name="restartconfig",
        description="Shows the current server restart configuration."
    )
    async def restartconfig(
        self,
        interaction: discord.Interaction
    ):
        """Display the current configuration."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        config = self.get_config(interaction.guild.id)

        parsed = self.parse_time(config["restart_time"])

        if parsed:
            hour, minute = parsed

            formatted_time = datetime(
                2000,
                1,
                1,
                hour,
                minute
            ).strftime("%I:%M %p")
        else:
            formatted_time = config["restart_time"]

        embed = discord.Embed(
            title="⚙️ Restart Configuration",
            description=(
                f"Current restart settings for **{interaction.guild.name}**."
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="⏱️ Interval",
            value=ALLOWED_INTERVALS.get(
                config["interval"],
                f"Every {config['interval']} Hours"
            ),
            inline=True
        )

        embed.add_field(
            name="🕐 Start Time",
            value=formatted_time,
            inline=True
        )

        embed.add_field(
            name="🌎 Timezone",
            value=f"`{config['timezone']}`",
            inline=True
        )

        embed.add_field(
            name="📋 Configuration",
            value=(
                f"```text\n"
                f"Interval : Every {config['interval']} hours\n"
                f"Start    : {config['restart_time']}\n"
                f"Timezone : {config['timezone']}\n"
                f"```"
            ),
            inline=False
        )

        embed.set_footer(
            text="Only server administrators can change restart settings."
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # COMMAND: RESTART RESET
    # =====================================================

    @app_commands.command(
        name="restartreset",
        description="Reset the server restart schedule to the default settings."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def restartreset(
        self,
        interaction: discord.Interaction
    ):
        """Reset restart configuration."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        guild_id = str(interaction.guild.id)

        if guild_id in self.configs:
            del self.configs[guild_id]
            await self.save_configs()

        embed = discord.Embed(
            title="🔄 Restart Schedule Reset",
            description=(
                f"**{interaction.guild.name}** has been reset "
                f"to the default restart schedule."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="⏱️ Interval",
            value="Every 2 Hours",
            inline=True
        )

        embed.add_field(
            name="🕐 Start Time",
            value="8:00 PM",
            inline=True
        )

        embed.add_field(
            name="🌎 Timezone",
            value="`America/New_York`",
            inline=True
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =====================================================
    # ERROR HANDLER
    # =====================================================

    @restartsetup.error
    async def restartsetup_error(
        self,
        interaction: discord.Interaction,
        error
    ):
        if isinstance(
            error,
            app_commands.errors.MissingPermissions
        ):
            await interaction.response.send_message(
                "❌ You need **Administrator** permissions to configure the server restart schedule.",
                ephemeral=True
            )
            return

        raise error

    @restartreset.error
    async def restartreset_error(
        self,
        interaction: discord.Interaction,
        error
    ):
        if isinstance(
            error,
            app_commands.errors.MissingPermissions
        ):
            await interaction.response.send_message(
                "❌ You need **Administrator** permissions to reset the server restart schedule.",
                ephemeral=True
            )
            return

        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(RestartInfo(bot))
