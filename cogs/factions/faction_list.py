import discord
from discord import app_commands
from discord.ext import commands
import logging

from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table, make_embed

log = logging.getLogger("dayz-manager")

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]

class FactionList(commands.Cog):
    """Lists active factions for a guild."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="list-factions",
        description="List active factions (optionally filtered by map)."
    )
    @app_commands.choices(map=MAP_CHOICES)
    @app_commands.describe(map="Optional map filter")
    async def list_factions(
        self,
        interaction: discord.Interaction,
        map: app_commands.Choice[str] | None = None,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await utils.ensure_connection()
            await ensure_faction_table()
        except Exception as e:
            log.error(f"❌ DB connection failed in {interaction.guild.name}: {e}", exc_info=True)
            return await interaction.followup.send(
                "❌ Failed to connect to the database.", ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = map.value.lower() if map else None

        try:
            async with utils.safe_acquire() as conn:
                if map_key:
                    rows = await conn.fetch(
                        """
                        SELECT faction_name, map, role_id, leader_id, member_ids, claimed_flag
                        FROM factions
                        WHERE guild_id=$1 AND map=$2
                        ORDER BY faction_name ASC
                        """,
                        guild_id, map_key
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT faction_name, map, role_id, leader_id, member_ids, claimed_flag
                        FROM factions
                        WHERE guild_id=$1
                        ORDER BY map ASC, faction_name ASC
                        """,
                        guild_id
                    )
        except Exception as e:
            log.error(f"❌ Failed to fetch factions for {guild.name}: {e}", exc_info=True)
            return await interaction.followup.send(
                "❌ Failed to fetch faction list. Please try again later.", ephemeral=True
            )

        if not rows:
            text = "No factions found for this map." if map_key else "No factions found."
            return await interaction.followup.send(text, ephemeral=True)

        embed = discord.Embed(
            title="🏳️ Active Factions",
            color=discord.Color.blue()
        )

        # Group factions by map for readability
        factions_by_map = {}
        for row in rows:
            row_map = (row["map"] or "Unknown").title()
            factions_by_map.setdefault(row_map, []).append(row)

        for map_name, factions in factions_by_map.items():
            for row in factions:
                faction_name = row["faction_name"]
                role_id = row["role_id"]
                leader_id = row["leader_id"]
                member_ids = list(row["member_ids"] or [])
                claimed_flag = row["claimed_flag"] or "—"

                role = guild.get_role(int(role_id)) if role_id else None
                role_mention = role.mention if role else "None"
                status = "✅" if role else "⚠️"

                leader_mention = f"<@{leader_id}>" if leader_id else "Unknown"
                unique_members = {str(mid) for mid in member_ids if mid}
                if leader_id:
                    unique_members.add(str(leader_id))
                member_count = len(unique_members)

                # Add a separate field per faction
                embed.add_field(
                    name=f"{status} {faction_name} • {map_name}",
                    value=(
                        f"**Role:** {role_mention}\n"
                        f"**Leader:** {leader_mention}\n"
                        f"**Members:** {member_count}\n"
                        f"**Flag:** `{claimed_flag}`"
                    ),
                    inline=False
                )

        await interaction.followup.send(embed=embed, ephemeral=True)
        log.info(f"✅ {interaction.user} listed factions in {guild.name} ({map_key or 'all maps'})")


async def setup(bot: commands.Bot):
    await bot.add_cog(FactionList(bot))
