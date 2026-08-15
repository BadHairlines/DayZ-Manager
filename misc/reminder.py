import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re


class Reminder(commands.Cog):
    """Create personal channel reminders."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="reminder",
        description="Set a reminder that will be posted in this channel."
    )
    @app_commands.describe(
        time="How long until the reminder.",
        message="What you want to be reminded about."
    )
    @app_commands.choices(
        time=[
            app_commands.Choice(name="30 Seconds", value="30s"),
            app_commands.Choice(name="1 Minute", value="1m"),
            app_commands.Choice(name="5 Minutes", value="5m"),
            app_commands.Choice(name="10 Minutes", value="10m"),
            app_commands.Choice(name="15 Minutes", value="15m"),
            app_commands.Choice(name="30 Minutes", value="30m"),
            app_commands.Choice(name="1 Hour", value="1h"),
            app_commands.Choice(name="2 Hours", value="2h"),
            app_commands.Choice(name="6 Hours", value="6h"),
            app_commands.Choice(name="12 Hours", value="12h"),
            app_commands.Choice(name="1 Day", value="1d"),
            app_commands.Choice(name="2 Days", value="2d"),
            app_commands.Choice(name="3 Days", value="3d"),
            app_commands.Choice(name="7 Days", value="7d"),
            app_commands.Choice(name="14 Days", value="14d"),
            app_commands.Choice(name="30 Days", value="30d"),
        ]
    )
    async def reminder(
        self,
        interaction: discord.Interaction,
        time: app_commands.Choice[str],
        message: str
    ):
        # Get the selected time value
        time_value = time.value

        # Convert the time into seconds
        match = re.fullmatch(
            r"\s*(\d+)\s*(s|m|h|d)\s*",
            time_value.lower()
        )

        if not match:
            return await interaction.response.send_message(
                "❌ Invalid reminder time.",
                ephemeral=True
            )

        amount = int(match.group(1))
        unit = match.group(2)

        # Prevent invalid/zero reminders
        if amount <= 0:
            return await interaction.response.send_message(
                "❌ The reminder time must be greater than 0.",
                ephemeral=True
            )

        # Convert to seconds
        multipliers = {
            "s": 1,
            "m": 60,
            "h": 60 * 60,
            "d": 60 * 60 * 24
        }

        delay = amount * multipliers[unit]

        # Limit reminders to 30 days
        if delay > 30 * 24 * 60 * 60:
            return await interaction.response.send_message(
                "❌ Reminders can only be set for up to **30 days**.",
                ephemeral=True
            )

        # Respond immediately
        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=(
                f"**Reminder:** {message}\n"
                f"**Time:** `{time.name}`\n\n"
                "I'll remind you in this channel when it's due."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

        # Save the channel where the command was used
        channel = interaction.channel

        # Wait until reminder is due
        await asyncio.sleep(delay)

        # Send the reminder in the same channel
        try:
            reminder_embed = discord.Embed(
                title="⏰ Reminder",
                description=message,
                color=discord.Color.blurple()
            )

            reminder_embed.add_field(
                name="Set For",
                value=f"`{time.name}`",
                inline=True
            )

            reminder_embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )

            reminder_embed.timestamp = discord.utils.utcnow()

            await channel.send(
                content=interaction.user.mention,
                embed=reminder_embed
            )

        except discord.Forbidden:
            print(
                f"❌ Could not send reminder in channel "
                f"{channel.id}."
            )

        except discord.HTTPException as e:
            print(
                f"❌ Failed to send reminder in channel "
                f"{channel.id}: {e}"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
