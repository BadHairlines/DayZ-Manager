import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table, make_embed

log = logging.getLogger("dayz-manager")

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]


async def flag_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=flag, value=flag)
        for flag in utils.FLAGS
        if current.lower() in flag.lower()
    ][:25]


sync_group = app_commands.Group(
    name="sync",
    description="Sync existing DayZ factions into the bot."
)


@sync_group.command(
    name="faction",
    description="Sync an existing faction (role + channel) into the DB."
)
@app_commands.choices(map=MAP_CHOICES)
@app_commands.autocomplete(flag=flag_autocomplete)
async def sync_faction(
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
        return await interaction.followup.send("❌ Guild only command.", ephemeral=True)

    if not interaction.user.guild_permissions.administrator:
        return await interaction.followup.send("🚫 Admin only.", ephemeral=True)

    await utils.ensure_connection()
    await ensure_faction_table()

    guild_id = str(guild.id)
    map_key = map.value.lower()
    faction_name = role.name

    members = [m for m in guild.members if role in m.roles]

    if leader is None:
        leader = interaction.user if role in interaction.user.roles else (members[0] if members else None)

    if leader is None:
        return await interaction.followup.send(
            "❌ Could not determine leader. Please specify one.",
            ephemeral=True
        )

    role_color = role.color if role.color.value != 0 else discord.Color(0x2ECC71)

    try:
        async with utils.safe_acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                guild_id, faction_name
            )

        if existing:
            return await interaction.followup.send(
                f"⚠️ Faction already exists (map: `{existing['map']}`).",
                ephemeral=True
            )

        claimed_flag = None
        if flag:
            flags = await utils.get_all_flags(guild_id, map_key)
            flag_row = next((f for f in flags if f["flag"].lower() == flag.lower()), None)

            if not flag_row:
                return await interaction.followup.send("🚫 Flag not found.", ephemeral=True)

            if flag_row["status"] == "❌":
                return await interaction.followup.send(
                    f"⚠️ Flag already owned by <@&{flag_row['role_id']}>.",
                    ephemeral=True
                )

            claimed_flag = flag_row["flag"]

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

        # Update flag system (NO LOG CHANNELS)
        if claimed_flag:
            await utils.set_flag(guild_id, map_key, claimed_flag, "❌", str(role.id))

            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id,
                    map_key,
                )

            if row:
                ch = guild.get_channel(int(row["channel_id"]))
                if ch:
                    try:
                        msg = await ch.fetch_message(int(row["message_id"]))
                        embed = await utils.create_flag_embed(guild_id, map_key)
                        await msg.edit(embed=embed)
                    except Exception as e:
                        log.warning(f"Flag embed refresh failed: {e}")

        members_mentions = ", ".join(m.mention for m in members) or "*None*"

        embed = make_embed(
            "__Faction Synced__",
            (
                f"✅ **{faction_name}** synced successfully.\n\n"
                f"🗺️ Map: `{map.value}`\n"
                f"🎭 Role: {role.mention}\n"
                f"🏠 Channel: {channel.mention}\n"
                f"👑 Leader: {leader.mention}\n"
                f"🏳️ Flag: `{claimed_flag or 'None'}`\n\n"
                f"👥 Members: {members_mentions}\n"
                f"🕓 Synced: <t:{int(datetime.utcnow().timestamp())}:f>"
            ),
            color=role_color.value,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

        log.info(
            f"Synced faction '{faction_name}' ({map_key}) in {guild.name} "
            f"Members={len(members)} Flag={claimed_flag or 'None'}"
        )

    except Exception as e:
        log.error(f"Sync failed in {guild.name}: {e}", exc_info=True)
        await interaction.followup.send(f"❌ Sync failed:\n```{e}```", ephemeral=True)


class FactionSync(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    bot.tree.add_command(sync_group)
    await bot.add_cog(FactionSync(bot))
