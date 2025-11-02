import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs import utils  # ✅ use full utils module for shared logging
from .faction_utils import ensure_faction_table, make_embed


class FactionInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================
    # 🔍 /faction-info
    # ============================================
    @app_commands.command(name="faction-info", description="View details about a specific faction.")
    async def faction_info(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=False)
        await ensure_faction_table()

        # 🧩 Check DB
        if utils.db_pool is None:
            return await interaction.followup.send("❌ Database not initialized yet.", ephemeral=True)

        guild = interaction.guild

        # 🔍 Fetch faction
        async with utils.db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), name
            )

        if not faction:
            return await interaction.followup.send(f"❌ Faction `{name}` not found.", ephemeral=True)

        # 🧱 Fetch Discord entities
        leader = guild.get_member(int(faction["leader_id"])) if faction["leader_id"] else None
        members = []
        for mid in (faction["member_ids"] or []):
            m = guild.get_member(int(mid))
            if m:
                members.append(m.mention)

        role = guild.get_role(int(faction["role_id"])) if faction["role_id"] else None
        channel = guild.get_channel(int(faction["channel_id"])) if faction["channel_id"] else None
        color = int(faction["color"].strip("#"), 16) if faction["color"] else 0x2ECC71

        # 🕓 Creation time handling
        created_ts = None
        if faction.get("created_at"):
            try:
                created_ts = int(datetime.timestamp(faction["created_at"]))
            except Exception:
                created_ts = None

        # 📜 Build embed
        embed = discord.Embed(
            title=f"🎭 {faction['faction_name']} — Overview",
            color=color,
            description=f"🗺️ **Map:** `{faction['map']}`"
        )

        embed.add_field(name="👑 Leader", value=leader.mention if leader else "*Unknown*", inline=False)
        embed.add_field(name="👥 Members", value="\n".join(members) or "*No members listed*", inline=False)
        embed.add_field(name="🎨 Color", value=f"`{faction['color']}`", inline=True)
        embed.add_field(name="🏠 Channel", value=channel.mention if channel else "*Deleted*", inline=True)
        embed.add_field(name="🎭 Role", value=role.mention if role else "*Deleted*", inline=True)
        if created_ts:
            embed.add_field(name="🕓 Created", value=f"<t:{created_ts}:f>", inline=False)

        embed.set_footer(
            text="DayZ Manager • Faction Overview",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await interaction.followup.send(embed=embed)

        # 🪵 Log the info view (optional but useful)
        await utils.log_faction_action(
            guild,
            action="Faction Viewed",
            faction_name=faction["faction_name"],
            user=interaction.user,
            details=f"{interaction.user.mention} viewed information for `{faction['faction_name']}`."
        )


async def setup(bot):
    await bot.add_cog(FactionInfo(bot))
