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
        time="How long until the reminder (e.g. 30m, 2h, 1d).",
        message="What you want to be reminded about."
    )
    async def reminder(
        self,
        interaction: discord.Interaction,
        time: str,
        message: str
    ):
        # Convert the time into seconds
        match = re.fullmatch(
            r"\s*(\d+)\s*(s|m|h|d)\s*",
            time.lower()
        )

        if not match:
            return await interaction.response.send_message(
                "❌ Invalid time format.\n"
                "Use something like `30s`, `15m`, `2h`, or `1d`.",
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
                f"**Time:** `{time}`\n\n"
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
                value=f"`{time}`",
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
