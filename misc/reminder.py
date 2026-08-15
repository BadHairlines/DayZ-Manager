import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re


class Reminder(commands.Cog):
    """Create personal DM reminders."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="reminder",
        description="Set a personal reminder that will be sent to you by DM."
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

        # Try to DM the user immediately to confirm DMs are available
        try:
            test_embed = discord.Embed(
                title="⏰ Reminder Set",
                description=(
                    f"**Reminder:** {message}\n"
                    f"**Time:** `{time}`\n\n"
                    "I'll DM you when your reminder is due."
                ),
                color=discord.Color.blurple()
            )

            test_embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )

            test_embed.timestamp = discord.utils.utcnow()

            await interaction.user.send(embed=test_embed)

        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ **I couldn't DM you.**\n\n"
                "Please make sure your Discord DMs are enabled for this "
                "server, then try the reminder again.",
                ephemeral=True
            )

        except discord.HTTPException as e:
            print(
                f"Failed to test DM for {interaction.user} "
                f"({interaction.user.id}): {e}"
            )

            return await interaction.response.send_message(
                "❌ I couldn't send you a DM right now. "
                "Please try again later.",
                ephemeral=True
            )

        # Send confirmation in the server
        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=(
                f"**Reminder:** {message}\n"
                f"**Time:** `{time}`\n\n"
                "✅ DM delivery confirmed.\n"
                "I'll remind you when it's due."
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

        # Wait until reminder is due
        await asyncio.sleep(delay)

        # Send the actual reminder
        try:
            dm_embed = discord.Embed(
                title="⏰ Reminder",
                description=message,
                color=discord.Color.blurple()
            )

            dm_embed.add_field(
                name="Set For",
                value=f"`{time}`",
                inline=True
            )

            dm_embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )

            dm_embed.timestamp = discord.utils.utcnow()

            await interaction.user.send(embed=dm_embed)

            print(
                f"Reminder sent to {interaction.user} "
                f"({interaction.user.id})"
            )

        except discord.Forbidden:
            print(
                f"❌ Could not DM reminder to {interaction.user} "
                f"({interaction.user.id})."
            )

        except discord.HTTPException as e:
            print(
                f"❌ Failed to send reminder to {interaction.user} "
                f"({interaction.user.id}): {e}"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
