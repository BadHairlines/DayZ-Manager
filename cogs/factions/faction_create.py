import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import logging
from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table, make_embed

log = logging.getLogger("dayz-manager")

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
    @app_commands.describe(
        name="Name of the faction",
        map="Select which map this faction belongs to",
        flag="Select the flag this faction will claim",
        color="Choose the faction color",
        leader="Select the faction leader",
        member1="Faction member #1 (optional)",
        member2="Faction member #2 (optional)",
        member3="Faction member #3 (optional)"
    )
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

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("🚫 Only admins can create factions.", ephemeral=True)

        await utils.ensure_connection()
        await ensure_faction_table()

        lock_key = f"{guild_id}:{map_key}"
        lock = self._locks.setdefault(lock_key, discord.utils.MISSING)
        if lock is discord.utils.MISSING:
            import asyncio
            lock = asyncio.Lock()
            self._locks[lock_key] = lock

        async with lock:
            try:
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

                flags = await utils.get_all_flags(guild_id, map_key)
                flag_data = next((f for f in flags if f["flag"].lower() == flag.lower()), None)
                if not flag_data:
                    return await interaction.followup.send(
                        f"🚫 Flag `{flag}` not found on `{map_key}`.", ephemeral=True
                    )
                if flag_data["status"] == "❌":
                    current_owner = flag_data["role_id"]
                    return await interaction.followup.send(
                        f"⚠️ Flag `{flag}` is already owned by <@&{current_owner}>.",
                        ephemeral=True
                    )

                category_name = f"🌍 {map.value} Factions Hub"
                category = discord.utils.get(guild.categories, name=category_name) or await guild.create_category(category_name)

                role = await guild.create_role(name=name, color=role_color, mentionable=True)
                divider = discord.utils.get(guild.roles, name="────────── Factions ──────────")
                if divider:
                    try:
                        await role.edit(position=divider.position - 1)
                    except discord.Forbidden:
                        log.warning(f"Missing permission to reposition role {role.name} in {guild.name}.")

                channel_name = name.lower().replace(" ", "-")

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=False
                    ),
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
                        log.warning(f"Could not assign {role.name} to {m.display_name} in {guild.name}.")

                async with utils.safe_acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO factions (guild_id, map, faction_name, role_id, channel_id, leader_id, member_ids, color)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                        """,
                        guild_id, map_key, name, str(role.id), str(channel.id),
                        str(leader.id), [str(m.id) for m in members], color.value
                    )

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
                    log.warning(f"⚠️ Failed to update flag embed for {guild.name}/{map_key}: {e}")

                members_list = "\n".join([m.mention for m in members if m.id != leader.id]) or "*No members listed*"
                welcome_embed = discord.Embed(
                    title=f"🎖️ Welcome to {name}!",
                    description=(
                        f"Welcome to your **{map.value} HQ**, {role.mention}! ⚔️\n\n"
                        f"👑 **Leader:** {leader.mention}\n"
                        f"👥 **Members:**\n{members_list}\n\n"
                        f"🏳️ **Claimed Flag:** `{flag}`\n"
                        f"🎨 **Color:** `{color.name}`\n"
                        f"🕓 **Created:** <t:{int(datetime.utcnow().timestamp())}:f>"
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

                await utils.log_faction_action(
                    guild,
                    action="Faction Created + Flag Claimed",
                    faction_name=name,
                    user=interaction.user,
                    details=f"Leader: {leader.mention}, Map: {map.value}, Flag: {flag}, Members: {', '.join([m.mention for m in members])}",
                    map_key=map_key,
                )

                confirm_embed = make_embed(
                    "__Faction Created__",
                    f"🗺️ **Map:** `{map.value}`\n"
                    f"🏳️ **Flag:** `{flag}`\n"
                    f"🎭 **Role:** {role.mention}\n"
                    f"🏠 **Channel:** {channel.mention}\n"
                    f"👑 **Leader:** {leader.mention}\n\n"
                    f"👥 **Members:** {', '.join([m.mention for m in members]) or '*None*'}\n\n"
                    f"🎨 **Color:** `{color.name}`\n"
                    f"🕓 **Created:** <t:{int(datetime.utcnow().timestamp())}:f>",
                    color=int(color.value.strip("#"), 16)
                )
                await interaction.followup.send(embed=confirm_embed)
                log.info(f"✅ Created faction '{name}' ({map_key}) in {guild.name}.")

            except Exception as e:
                log.error(f"❌ Faction creation failed in {guild.name}: {e}", exc_info=True)
                await interaction.followup.send(f"❌ Faction creation failed:\n```{e}```", ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionCreate(bot))
