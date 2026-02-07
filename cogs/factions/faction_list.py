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
    """Lists active factions for any guild."""

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
        # Only works in a guild
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = map.value.lower() if map else None

        # Fetch factions
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
            log.error(f"❌ Failed to fetch faction list for {guild.name}: {e}", exc_info=True)
            return await interaction.followup.send(
                "❌ Failed to fetch faction list. Please try again later.", ephemeral=True
            )

        if not rows:
            text = "No factions found for this map." if map_key else "No factions found."
            return await interaction.followup.send(text, ephemeral=True)

        # Build the list
        lines = []
        for row in rows:
            faction_name = row["faction_name"]
            row_map = (row["map"] or "").title()
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

            map_label = f" • {row_map}"  # always show map
            lines.append(
                f"{status} **{faction_name}**{map_label} — "
                f"Role: {role_mention} • Leader: {leader_mention} • Members: {member_count} • Flag: `{claimed_flag}`"
            )

        embed = make_embed("🏳️ Active Factions", "\n".join(lines))
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add the cog and immediately sync to the current guild for instant visibility."""
    await bot.add_cog(FactionList(bot))
    try:
        # Sync to all guilds the bot is currently in
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
            log.info(f"✅ Synced list-factions in guild: {guild.name} ({guild.id})")
    except Exception as e:
        log.error(f"❌ Failed to sync list-factions: {e}")
