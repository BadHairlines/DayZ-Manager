import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import logging
from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table, make_embed

log = logging.getLogger("dayz-manager")

ALLOWED_ROLES = [1109306236110909567, 1374649617320251442]

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]

COLOR_CHOICES = [
    app_commands.Choice(name="Red ❤️", value="#FF0000"),
    app_commands.Choice(name="Orange 🧡", value="#FFA500"),
    app_commands.Choice(name="Yellow 💛", value="#FFFF00"),
    app_commands.Choice(name="Green 💚", value="#00FF00"),
    app_commands.Choice(name="Blue 💙", value="#0000FF"),
    app_commands.Choice(name="Purple 💜", value="#800080"),
    app_commands.Choice(name="Pink 💖", value="#FF69B4"),
    app_commands.Choice(name="Cyan 💎", value="#00FFFF"),
    app_commands.Choice(name="White 🤍", value="#FFFFFF"),
    app_commands.Choice(name="Black 🖤", value="#000000"),
    app_commands.Choice(name="Grey ⚙️", value="#808080"),
    app_commands.Choice(name="Brown 🤎", value="#8B4513"),
]


class FactionCreate(commands.Cog):
    """Handles creation of factions with flag claiming and HQ setup."""

    def __init__(self, bot):
        self.bot = bot
        self._locks = {}

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in utils.FLAGS if current.lower() in flag.lower()
        ][:25]

    @app_commands.command(
        name="create-faction",
        description="Create a faction, assign a flag, and set up its role and HQ."
    )
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def create_faction(
        self,
        interaction: discord.Interaction,
        name: str,
        map: app_commands.Choice[str],
        flag: str,
        color: app_commands.Choice[str],
        leader: discord.Member,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
    ):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = map.value.lower()
        role_color = discord.Color(int(color.value.strip("#"), 16))

        if not any(role.id in ALLOWED_ROLES for role in interaction.user.roles):
            return await interaction.followup.send(
                "🚫 You don't have permission to create factions.",
                ephemeral=True
            )

        await utils.ensure_connection()
        await ensure_faction_table()

        lock_key = f"{guild_id}:{map_key}"
        import asyncio
        lock = self._locks.setdefault(lock_key, asyncio.Lock())

        async with lock:

            # check duplicate faction
            async with utils.safe_acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                    guild_id, name
                )
            if existing:
                return await interaction.followup.send(
                    f"⚠️ Faction **{name}** already exists on {existing['map']}!",
                    ephemeral=True
                )

            # validate flag
            flags = await utils.get_all_flags(guild_id, map_key)
            flag_data = next((f for f in flags if f["flag"].lower() == flag.lower()), None)

            if not flag_data:
                return await interaction.followup.send(
                    f"🚫 Flag `{flag}` not found on `{map_key}`.",
                    ephemeral=True
                )

            if flag_data["status"] == "❌":
                return await interaction.followup.send(
                    f"⚠️ Flag `{flag}` is already owned by <@&{flag_data['role_id']}>.",
                    ephemeral=True
                )

            # category + role
            category_name = f"🌍 {map.value} Factions Hub"
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name)

            role = await guild.create_role(
                name=name,
                color=role_color,
                mentionable=True
            )

            channel_name = name.lower().replace(" ", "-")

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    add_reactions=True,
                    attach_files=True,
                    embed_links=True,
                    use_application_commands=True,
                ),
            }

            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                topic=f"Private HQ for {name} faction on {map.value}.",
                overwrites=overwrites,
            )

            members = [m for m in [leader, member1, member2, member3] if m]

            for m in members:
                try:
                    await m.add_roles(role)
                except discord.Forbidden:
                    log.warning(f"Could not assign role to {m.display_name} in {guild.name}")

            # DB insert
            async with utils.safe_acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO factions (guild_id, map, faction_name, role_id, channel_id, leader_id, member_ids, color)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                    """,
                    guild_id, map_key, name,
                    str(role.id), str(channel.id),
                    str(leader.id),
                    [str(m.id) for m in members],
                    color.value
                )

            # flag update
            await utils.set_flag(guild_id, map_key, flag, "❌", str(role.id))

            async with utils.safe_acquire() as conn:
                await conn.execute(
                    """
                    UPDATE factions
                    SET claimed_flag=$1
                    WHERE guild_id=$2 AND role_id=$3 AND map=$4
                    """,
                    flag, guild_id, str(role.id), map_key
                )

            # update embed (NO LOGGING ANYWHERE)
            try:
                embed = await utils.create_flag_embed(guild_id, map_key)
                async with utils.safe_acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                        guild_id, map_key
                    )

                if row:
                    ch = guild.get_channel(int(row["channel_id"]))
                    msg = await ch.fetch_message(int(row["message_id"]))
                    await msg.edit(embed=embed)

            except Exception as e:
                log.warning(f"Failed to update flag embed: {e}")

            # HQ embed
            members_list = "\n".join([m.mention for m in members if m.id != leader.id]) or "*No members listed*"

            welcome_embed = discord.Embed(
                title=f"🎖️ Welcome to {name}!",
                description=(
                    f"Welcome to your **{map.value} HQ**, {role.mention}! ⚔️\n\n"
                    f"👑 Leader: {leader.mention}\n"
                    f"👥 Members:\n{members_list}\n\n"
                    f"🏳️ Flag: `{flag}`\n"
                    f"🎨 Color: `{color.name}`\n"
                    f"🕓 Created: <t:{int(datetime.utcnow().timestamp())}:f>"
                ),
                color=role_color
            )

            welcome_embed.set_footer(
                text=f"{map.value} • Faction HQ",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )

            msg = await channel.send(embed=welcome_embed)

            try:
                await msg.pin()
            except discord.Forbidden:
                pass

            # console only (replaces ALL logging system)
            log.info(
                f"Faction Created | {name} | {map_key} | "
                f"Leader: {leader.display_name} | Flag: {flag}"
            )

            confirm_embed = make_embed(
                "__Faction Created__",
                f"🗺️ Map: `{map.value}`\n"
                f"🏳️ Flag: `{flag}`\n"
                f"🎭 Role: {role.mention}\n"
                f"🏠 Channel: {channel.mention}\n"
                f"👑 Leader: {leader.mention}\n\n"
                f"👥 Members: {', '.join([m.mention for m in members]) or '*None*'}\n\n"
                f"🎨 Color: `{color.name}`\n"
                f"🕓 Created: <t:{int(datetime.utcnow().timestamp())}:f>",
                color=int(color.value.strip("#"), 16)
            )

            await interaction.followup.send(embed=confirm_embed)


async def setup(bot):
    await bot.add_cog(FactionCreate(bot))
