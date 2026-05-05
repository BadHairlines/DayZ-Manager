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
        author_icon: str | None = None,
        author_name: str | None = None
    ) -> discord.Embed:
        """Standardized embed builder."""

        # -----------------------------
        # SAFETY: description limit
        # -----------------------------
        if desc and len(desc) > self.MAX_DESC_LENGTH:
            desc = desc[: self.MAX_DESC_LENGTH - 1] + "…"

        embed = discord.Embed(
            title=title,
            description=desc or "",
            color=color
        )

        # -----------------------------
        # AUTHOR (SAFE OPTIONAL)
        # -----------------------------
        if author_name:
            name = author_name
            if author_icon:
                name = f"{author_icon} {author_name}"
            embed.set_author(name=name)

        # -----------------------------
        # FOOTER
        # -----------------------------
        embed.set_footer(
            text=self.FOOTER_TEXT,
            icon_url=self.FOOTER_ICON
        )

        embed.timestamp = discord.utils.utcnow()

        return embed
