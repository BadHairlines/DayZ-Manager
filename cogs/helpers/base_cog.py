import logging
import discord
from datetime import datetime

from cogs import utils

log = logging.getLogger("dayz-manager")


class BaseCog:
    """Reusable base cog with embed utilities only (no system-specific logic)."""

    def make_embed(
        self,
        title: str,
        desc: str,
        color: int,
        author_icon: str,
        author_name: str
    ) -> discord.Embed:
        """Create a standardized embed for the bot."""

        if len(desc) > 4000:
            desc = desc[:3990] + "…"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color
        )

        embed.set_author(name=f"{author_icon} {author_name}")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        embed.timestamp = discord.utils.utcnow()
        return embed
