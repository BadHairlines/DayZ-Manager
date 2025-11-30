import os
import random
import discord
from discord import app_commands
from discord.ext import commands


SUGGESTIONS_CHANNEL_ENV = "SUGGESTIONS_CHANNEL_ID"  # optional env var


class Suggestions(commands.Cog):
    """Handles user suggestions with a polished embed + reactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Small helper to resolve the suggestions channel
    def _get_suggestions_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        # 1) Prefer explicit channel ID via environment variable (if set)
        chan_id = os.getenv(SUGGESTIONS_CHANNEL_ENV)
        if chan_id and chan_id.isdigit():
            ch = guild.get_channel(int(chan_id))
            if isinstance(ch, discord.TextChannel):
                return ch

        # 2) Fallback: try common suggestion channel names
        possible_names = [
            "💡・suggestions",
            "💡suggestions",
            "suggestions",
            "server-suggestions",
        ]
        for name in possible_names:
            ch = discord.utils.get(guild.text_channels, name=name)
            if isinstance(ch, discord.TextChannel):
                return ch

        # 3) If none found, just use the system channel (or None)
        return guild.system_channel

    @app_commands.command(
        name="suggest",
        description="Submit a suggestion for the server."
    )
    @app_commands.describe(
        suggestion="What would you like to suggest?"
    )
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        """Slash command to submit a suggestion."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return await interaction.followup.send(
                "❌ Suggestions can only be used inside a server.",
                ephemeral=True
            )

        guild = interaction.guild
        user = interaction.user

        # Resolve target channel
        target_channel = self._get_suggestions_channel(guild)
        if not target_channel:
            return await interaction.followup.send(
                "❌ I couldn't find a suggestions channel for this server.\n"
                "Ask an admin to set one up or define `SUGGESTIONS_CHANNEL_ID` in the bot environment.",
                ephemeral=True
            )

        # Build a nice embed
        embed = discord.Embed(
            title="💡 New Suggestion Submitted!",
            description=(
                f"**Suggestion:**\n"
                f"{suggestion}\n\n"
                f"**Suggested By:**\n"
                f"{user.mention} (`{user.id}`)"
            ),
            color=random.randint(0, 0xFFFFFF)
        )

        embed.set_footer(
            text="DayZ Manager | Suggestions",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()

        # Avoid pinging roles/users in the suggestion message
        allowed_mentions = discord.AllowedMentions.none()

        # Send to suggestions channel
        try:
            msg = await target_channel.send(
                embed=embed,
                allowed_mentions=allowed_mentions
            )
            # Add voting reactions
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I don't have permission to send messages or add reactions "
                f"in {target_channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Failed to post your suggestion:\n```{e}```",
                ephemeral=True
            )

        # Ephemeral confirmation to the user
        confirm_embed = discord.Embed(
            title="✅ Suggestion Submitted",
            description=(
                f"Your suggestion has been posted in {target_channel.mention}.\n\n"
                f"📝 **Preview:**\n{suggestion}"
            ),
            color=0x2ECC71
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
