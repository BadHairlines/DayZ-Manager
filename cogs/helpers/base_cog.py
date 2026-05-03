import discord


class BaseCog:
    """Shared utilities for all cogs (UI helpers only)."""

    MAX_DESC_LENGTH = 4000
    FOOTER_TEXT = "DayZ Manager"
    FOOTER_ICON = "https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"

    def make_embed(
        self,
        title: str,
        desc: str,
        color: int,
        author_icon: str,
        author_name: str
    ) -> discord.Embed:
        """Standardized embed builder."""

        if len(desc) > self.MAX_DESC_LENGTH:
            desc = desc[: self.MAX_DESC_LENGTH - 10] + "…"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color
        )

        embed.set_author(name=f"{author_icon} {author_name}")
        embed.set_footer(
            text=self.FOOTER_TEXT,
            icon_url=self.FOOTER_ICON
        )

        embed.timestamp = discord.utils.utcnow()
        return embed
