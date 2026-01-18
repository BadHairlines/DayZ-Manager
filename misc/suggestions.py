import random
import discord
from discord import app_commands
from discord.ext import commands


class Suggestions(commands.Cog):
    """Handles user suggestions as replies with embed + reactions + discussion threads."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_or_create_suggestions_channel(
        self, guild: discord.Guild
    ) -> discord.TextChannel | None:
        candidates = [
            c for c in guild.text_channels
            if "suggest" in c.name.lower()
        ]

        if candidates:
            def score(ch: discord.TextChannel) -> tuple[int, int]:
                name = ch.name.lower()
                if name == "❔┃suggestions":
                    rank = 0
                elif name == "suggestions":
                    rank = 1
                elif "suggestions" in name:
                    rank = 2
                else:
                    rank = 3
                return (rank, ch.position)

            return min(candidates, key=score)

        try:
            return await guild.create_text_channel(
                "❔┃suggestions",
                reason="Auto-created suggestions channel for /suggest"
            )
        except discord.Forbidden:
            return None
        except Exception as e:
            print(f"⚠️ Failed to create suggestions channel in {guild.name}: {e}")
            return None

    @app_commands.command(
        name="suggest",
        description="Submit a suggestion for the server."
    )
    @app_commands.describe(suggestion="What would you like to suggest?")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Suggestions can only be used inside a server.",
                ephemeral=True
            )

        user = interaction.user
        guild = interaction.guild

        # Get or create suggestions channel
        target_channel = await self._get_or_create_suggestions_channel(guild)
        if not target_channel:
            return await interaction.response.send_message(
                "❌ I couldn't find or create a `❔┃suggestions` channel. "
                "Please check my permissions.",
                ephemeral=True
            )

        # Build suggestion embed
        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=random.randint(0, 0xFFFFFF)
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.set_footer(
            text="DayZ Manager | Suggestions",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()

        allowed_mentions = discord.AllowedMentions.none()

        # Send suggestion as a reply
        try:
            msg = await interaction.followup.send(
                content=None,
                embed=embed,
                allowed_mentions=allowed_mentions,
                ephemeral=False  # visible in channel
            )
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Failed to post suggestion:\n```{e}```",
                ephemeral=True
            )

        # Add reactions (requires the sent message object)
        # For app_commands, interaction.followup.send returns None, so we fetch the last message
        try:
            last_msg = (await target_channel.history(limit=1).flatten())[0]
            await last_msg.add_reaction("👍")
            await last_msg.add_reaction("👎")

            # Create discussion thread
            thread_name = f"💬 {user.display_name}'s suggestion"
            thread = await last_msg.create_thread(
                name=thread_name,
                auto_archive_duration=1440
            )
            await thread.send(
                f"{user.mention} thanks for your suggestion! 🧠\n"
                "Use this thread to discuss, refine, or vote on the idea."
            )
        except Exception as e:
            print(f"⚠️ Could not add reactions or thread: {e}")

