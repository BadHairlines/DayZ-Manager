# cogs/faction_sync.py
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from cogs import utils
from .faction_utils import ensure_faction_table, make_embed

log = logging.getLogger("dayz-manager")

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]


class FactionSync(commands.Cog):
    """Sync manually-created factions into the DayZ Manager DB."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Re-use same flag autocomplete style
    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in utils.FLAGS
            if current.lower() in flag.lower()
        ][:25]

    @app_commands.command(
        name="sync-faction",
        description="Sync an existing faction (role + channel) into the bot."
    )
    @app_commands.choices(map=MAP_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    @app_commands.describe(
        map="Which map this faction belongs to",
        role="Existing faction role",
        channel="Existing faction HQ text channel",
        flag="Flag to claim for this faction (optional)",
        leader="Faction leader (optional, defaults to you or first member)"
    )
    async def sync_faction(
        self,
        interaction: discord.Interaction,
        map: app_commands.Choice[str],
        role: discord.Role,
        channel: discord.TextChannel,
        flag: str | None = None,
        leader: discord.Member | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if not guild:
            return await interaction.followup.send(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )

        # --- Admin check ---
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send(
                "🚫 Only admins can sync factions.",
                ephemeral=True,
            )

        await utils.ensure_connection()
        await ensure_faction_table()

        guild_id = str(guild.id)
        map_key = map.value.lower()

        # Faction name = role name (keeps things simple & consistent)
        faction_name = role.name

        # Auto-detect members = everyone who has that role
        members = [m for m in guild.members if role in m.roles]

        # Leader priority: explicit arg > interaction user (if they have role) > first member > None
        if leader is None:
            if role in interaction.user.roles:
                leader = interaction.user
            elif members:
                leader = members[0]

        if leader is None:
            return await interaction.followup.send(
                "❌ I couldn't determine a leader. Please specify one in the command.",
                ephemeral=True,
            )

        # Faction color from role color (fallback to green)
        role_color = role.color if role.color.value != 0 else discord.Color(0x2ECC71)

        try:
            # --- Check if faction already exists ---
            async with utils.safe_acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                    guild_id,
                    faction_name,
                )

            if existing:
                return await interaction.followup.send(
                    f"⚠️ Faction **{faction_name}** already exists in the database "
                    f"(map: `{existing['map']}`).",
                    ephemeral=True,
                )

            # --- Optional flag validation ---
            claimed_flag: str | None = None
            if flag:
                flags = await utils.get_all_flags(guild_id, map_key)
                flag_row = next(
                    (f for f in flags if f["flag"].lower() == flag.lower()),
                    None,
                )
                if not flag_row:
                    return await interaction.followup.send(
                        f"🚫 Flag `{flag}` not found on `{map_key}`.",
                        ephemeral=True,
                    )
                if flag_row["status"] == "❌":
                    current_owner = flag_row["role_id"]
                    return await interaction.followup.send(
                        f"⚠️ Flag `{flag}` is already owned by <@&{current_owner}>.",
                        ephemeral=True,
                    )

                claimed_flag = flag_row["flag"]  # use canonical case

            # --- Insert into DB ---
            member_ids = [str(m.id) for m in members]

            async with utils.safe_acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO factions (
                        guild_id, map, faction_name,
                        role_id, channel_id,
                        leader_id, member_ids,
                        color, claimed_flag
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    """,
                    guild_id,
                    map_key,
                    faction_name,
                    str(role.id),
                    str(channel.id),
                    str(leader.id),
                    member_ids,
                    f"#{role_color.value:06X}",
                    claimed_flag,
                )

            # --- Claim flag + refresh embed if a flag was provided ---
            if claimed_flag:
                await utils.set_flag(guild_id, map_key, claimed_flag, "❌", str(role.id))
                async with utils.safe_acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                        guild_id,
                        map_key,
                    )
                if row:
                    flag_ch = guild.get_channel(int(row["channel_id"]))
                    if flag_ch:
                        try:
                            msg = await flag_ch.fetch_message(int(row["message_id"]))
                            embed = await utils.create_flag_embed(guild_id, map_key)
                            await msg.edit(embed=embed)
                        except Exception as e:
                            log.warning(
                                f"⚠️ Failed to refresh flag embed during sync "
                                f"for {guild.name}/{map_key}: {e}"
                            )

            # --- Log to faction logs ---
            members_mentions = ", ".join(m.mention for m in members) or "*None*"
            details = (
                f"Leader: {leader.mention}\n"
                f"Map: `{map.value}`\n"
                f"Flag: `{claimed_flag or 'None'}`\n"
                f"Channel: {channel.mention}\n"
                f"Members: {members_mentions}"
            )

            await utils.log_faction_action(
                guild,
                action="Faction Synced (Manual)",
                faction_name=faction_name,
                user=interaction.user,
                details=details,
                map_key=map_key,
            )

            # --- Confirmation embed for the admin ---
            created_ts = int(datetime.utcnow().timestamp())
            confirm = make_embed(
                "__Faction Synced__",
                (
                    f"✅ **{faction_name}** has been synced into the DayZ Manager DB.\n\n"
                    f"🗺️ **Map:** `{map.value}`\n"
                    f"🎭 **Role:** {role.mention}\n"
                    f"🏠 **Channel:** {channel.mention}\n"
                    f"👑 **Leader:** {leader.mention}\n"
                    f"🏳️ **Flag:** `{claimed_flag or 'None'}`\n\n"
                    f"👥 **Members:** {members_mentions}\n\n"
                    f"🕓 **Synced:** <t:{created_ts}:f>"
                ),
                color=role_color.value,
            )
            await interaction.followup.send(embed=confirm, ephemeral=True)

            log.info(
                f"✅ Synced faction '{faction_name}' on {map_key} in {guild.name}. "
                f"Members: {len(members)}; Flag: {claimed_flag or 'None'}"
            )

        except Exception as e:
            log.error(f"❌ Faction sync failed in {guild.name}: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Faction sync failed:\n```{e}```",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(FactionSync(bot))
