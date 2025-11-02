import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs.utils import db_pool
from .faction_utils import ensure_faction_table, make_embed


class FactionInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="faction-info", description="View details about a specific faction.")
    async def faction_info(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=False)
        await ensure_faction_table()

        guild = interaction.guild
        async with db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), name
            )

        if not faction:
            return await interaction.followup.send(f"❌ Faction `{name}` not found.", ephemeral=True)

        # Fetch Discord objects
        leader = guild.get_member(int(faction["leader_id"]))
        members = []
        for mid in (faction["member_ids"] or []):
            member = guild.get_member(int(mid))
            if member:
                members.append(member.mention)

        role = guild.get_role(int(faction["role_id"]))
        channel = guild.get_channel(int(faction["channel_id"]))

        color = int(faction["color"].strip("#"), 16) if faction["color"] else 0x2ECC71
        created = faction["created_at"].strftime("%Y-%m-%d %H:%M:%S") if faction["created_at"] else "Unknown"

        # Embed Construction
        embed = discord.Embed(
            title=f"🎭 {faction['faction_name']} — Info",
            color=color,
            description=f"🗺️ **Map:** {faction['map']}"
        )

        embed.add_field(name="👑 Leader", value=leader.mention if leader else "*Unknown*", inline=False)
        embed.add_field(name="👥 Members", value="\n".join(members) or "*No members listed*", inline=False)
        embed.add_field(name="🎨 Color", value=f"`{faction['color']}`", inline=True)
        embed.add_field(name="🏠 Channel", value=channel.mention if channel else "*Deleted*", inline=True)
        embed.add_field(name="🎭 Role", value=role.mention if role else "*Deleted*", inline=True)
        embed.add_field(name="🕓 Created", value=f"<t:{int(datetime.timestamp(faction['created_at']))}:f>", inline=False)

        embed.set_footer(
            text="DayZ Manager — Faction Overview",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FactionInfo(bot))
