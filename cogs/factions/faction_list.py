import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import db_pool
from .faction_utils import ensure_faction_table, make_embed


MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]


class FactionList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="list-factions", description="List all factions for a specific map.")
    @app_commands.choices(map=MAP_CHOICES)
    async def list_factions(self, interaction: discord.Interaction, map: app_commands.Choice[str]):
        await interaction.response.defer(thinking=True)
        await ensure_faction_table()

        guild = interaction.guild
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT faction_name, leader_id, color, created_at FROM factions WHERE guild_id=$1 AND map=$2 ORDER BY created_at ASC",
                str(guild.id), map.value
            )

        if not rows:
            return await interaction.followup.send(f"⚠️ No factions found on `{map.value}`.", ephemeral=True)

        description_lines = []
        for row in rows:
            leader = guild.get_member(int(row["leader_id"])) if row["leader_id"] else None
            leader_mention = leader.mention if leader else "*Unknown*"
            color_tag = f"`{row['color']}`" if row["color"] else "`N/A`"
            created_timestamp = f"<t:{int(row['created_at'].timestamp())}:R>" if row["created_at"] else "Unknown"

            description_lines.append(
                f"🎭 **{row['faction_name']}** — {color_tag}\n👑 {leader_mention} • 🕓 {created_timestamp}"
            )

        embed = discord.Embed(
            title=f"🗺️ {map.value} Factions List",
            description="\n\n".join(description_lines),
            color=0x3498DB
        )
        embed.set_footer(
            text="DayZ Manager — Faction Overview",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FactionList(bot))
