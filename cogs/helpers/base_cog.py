from __future__ import annotations

import discord


class BaseCog:
    MAX_DESC_LENGTH = 4000
    FOOTER_TEXT = "DayZ Manager"
    FOOTER_ICON = "https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"

    def make_embed(
        self,
        title: str,
        desc: str = "",
        color: int = 0x3498DB,
        author_icon: str | None = None,
        author_name: str | None = None,
    ) -> discord.Embed:
        if len(desc) > self.MAX_DESC_LENGTH:
            desc = desc[: self.MAX_DESC_LENGTH - 1] + "…"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
        )

        if author_name:
            embed.set_author(
                name=f"{author_icon} {author_name}" if author_icon else author_name
            )

        embed.set_footer(
            text=self.FOOTER_TEXT,
            icon_url=self.FOOTER_ICON,
        )
        embed.timestamp = discord.utils.utcnow()
        return embed
