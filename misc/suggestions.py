import random
import discord
from discord import app_commands
from discord.ext import commands


class Suggestions(commands.Cog):
    """Handles user suggestions with a polished embed + reactions + discussion threads."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Small helper to resolve or create the suggestions channel
    async def _get_or_create_suggestions_channel(
        self,
        guild: discord.Guild
    ) -> discord.TextChannel | None:
        # Work only with real text channels
        text_channels = [
            c for c in guild.text_channels
            if isinstance(c, discord.TextChannel)
        ]

        # Candidates = channels whose name contains "suggest"
        candidates = [
            c for c in text_channels
            if "suggest" in c.name.lower()
        ]

        if candidates:
            # Prefer the "most correct" one:
            # 0 = exact "❔┃suggestions"
            # 1 = exact "suggestions"
            # 2 = contains "suggestions"
            # 3 = anything else containing "suggest"
            def channel_score(ch: discord.TextChannel) -> tuple[int, int]:
                name = ch.name.lower()

                if name == "❔┃suggestions".lower():
                    rank = 0
                elif name == "suggestions":
                    rank = 1
                elif "suggestions" in name:
                    rank = 2
                else:
                    rank = 3

                # Second key: channel position (higher in list = preferred)
                return (rank, ch.position)

            best = min(candidates, key=channel_score)
            return best

        # No suitable channel found, create one
        try:
            ch = await guild.create_text_channel(
                "❔┃suggestions",
                reason="Auto-created suggestions channel for /suggest"
            )
            return ch
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
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return await interaction.followup.send(
                "❌ Suggestions can only be used inside a server.",
                ephemeral=True
            )

        guild = interaction.guild
        user = interaction.user

        # Create or get suggestions channel
        target_channel = await self._get_or_create_suggestions_channel(guild)
        if not target_channel:
            return await interaction.followup.send(
                "❌ I couldn't find or create a `❔┃suggestions` channel.\n"
                "Please ensure I have permission to manage channels.",
                ephemeral=True
            )

        # Build cleaner embed
        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=random.randint(0, 0xFFFFFF)
        )

        # Author = user (avatar + name)
        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url,
        )

        embed.set_footer(
            text="DayZ Manager | Suggestions",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()

        # Prevent @ mentions inside the suggestion text from firing
        allowed_mentions = discord.AllowedMentions.none()

        # Send suggestion to suggestions channel
        try:
            msg = await target_channel.send(
                embed=embed,
                allowed_mentions=allowed_mentions
            )
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Failed to send suggestion:\n```{e}```",
                ephemeral=True
            )

        # Create a discussion thread off the suggestion message
        thread = None
        try:
            thread_name = f"💬 {user.display_name}'s suggestion"
            thread = await msg.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 24h archive; tweak if you want
            )
            # Starter message in thread
            await thread.send(
                f"{user.mention} thanks for your suggestion! 🧠\n"
                f"Use this thread to discuss, refine, or vote on the idea."
            )
        except discord.Forbidden:
            # No permission to create threads – silently ignore
            thread = None
        except Exception as e:
            print(f"⚠️ Failed to create discussion thread for suggestion in {guild.name}: {e}")
            thread = None

        # Ephemeral confirmation
        desc_lines = [
            f"Your suggestion has been posted in {target_channel.mention}."
        ]
        if thread:
            desc_lines.append(f"A discussion thread was created: {thread.mention}")

        confirm_embed = discord.Embed(
            title="✅ Suggestion Submitted",
            description="\n".join(desc_lines),
            color=0x2ECC71
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
