import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from dayz_manager.cogs.utils.database import db_pool
from dayz_manager.cogs.utils.embeds import create_flag_embed
from dayz_manager.cogs.utils.logging import log_faction_action
from dayz_manager.config import FLAGS as ALL_FLAGS
from .utils import ensure_faction_table, make_embed

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
    def __init__(self, bot):
        self.bot = bot

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=flag, value=flag) for flag in ALL_FLAGS if current.lower() in flag.lower()][:25]

    @app_commands.command(name="create-faction", description="Create a faction, assign a flag, and set up its role and HQ.")
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    @app_commands.describe(name="Name of the faction", map="Select which map this faction belongs to", flag="Select the flag this faction will claim", color="Choose the faction color", leader="Select the faction leader", member1="Faction member #1 (optional)", member2="Faction member #2 (optional)", member3="Faction member #3 (optional)")
    async def create_faction(self, interaction: discord.Interaction, name: str, map: app_commands.Choice[str], flag: str, color: app_commands.Choice[str], leader: discord.Member, member1: discord.Member | None = None, member2: discord.Member | None = None, member3: discord.Member | None = None):
        await interaction.response.defer(thinking=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Only admins can create factions.", ephemeral=True)

        if db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)

        map_key = map.value.lower()
        role_color = discord.Color(int(color.value.strip("#"), 16))

        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2", guild_id, name)
        if existing:
            return await interaction.followup.send(f"⚠️ Faction **{name}** already exists on {existing['map']}!", ephemeral=True)

        async with db_pool.acquire() as conn:
            flags = await conn.fetch("SELECT flag, status, role_id FROM flags WHERE guild_id=$1 AND map=$2 ORDER BY flag ASC;", guild_id, map_key)
        flag_data = next((f for f in flags if f["flag"].lower() == flag.lower()), None)
        if not flag_data:
            return await interaction.followup.send(f"🚫 Flag `{flag}` does not exist on `{map_key}`.", ephemeral=True)
        if flag_data["status"] == "❌":
            current_owner = flag_data["role_id"]
            return await interaction.followup.send(f"⚠️ Flag `{flag}` is already owned by <@&{current_owner}>.", ephemeral=True)

        category_name = f"{map.value} Factions Hub"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)

        role = await guild.create_role(name=name, color=role_color, mentionable=True)
        divider = discord.utils.get(guild.roles, name="────────── Factions ──────────")
        if divider:
            try:
                await role.edit(position=divider.position - 1)
            except Exception:
                pass

        channel_name = name.lower().replace(" ", "-")
        channel = await guild.create_text_channel(channel_name, category=category, topic=f"Private HQ for {name} faction on {map.value}.")
        await channel.set_permissions(role, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.default_role, read_messages=False)

        members = [m for m in [leader, member1, member2, member3] if m]
        for m in members:
            try:
                await m.add_roles(role)
            except Exception as e:
                print(f"⚠️ Failed to assign faction role to {m}: {e}")

        async with db_pool.acquire() as conn:
            await conn.execute("""                INSERT INTO factions (guild_id, map, faction_name, role_id, channel_id, leader_id, member_ids, color)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """, guild_id, map_key, name, str(role.id), str(channel.id), str(leader.id), [str(m.id) for m in members], color.value)

        async with db_pool.acquire() as conn:
            await conn.execute("""                INSERT INTO flags (guild_id, map, flag, status, role_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, map, flag)
                DO UPDATE SET status = EXCLUDED.status, role_id = EXCLUDED.role_id;
            """, guild_id, map_key, flag, "❌", str(role.id))
            await conn.execute("UPDATE factions SET claimed_flag=$1 WHERE guild_id=$2 AND role_id=$3 AND map=$4", flag, guild_id, str(role.id), map_key)

        try:
            embed = await create_flag_embed(guild_id, map_key)
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2", guild_id, map_key)
            if row:
                ch = guild.get_channel(int(row["channel_id"]))
                msg = await ch.fetch_message(int(row["message_id"])) if ch else None
                if msg:
                    await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Failed to update flag display: {e}")

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
        welcome_embed.set_footer(text=f"{map.value} • Faction HQ", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        msg = await channel.send(embed=welcome_embed)
        try:
            await msg.pin()
        except Exception:
            pass

        await log_faction_action(guild, action="Faction Created + Flag Claimed", faction_name=name, user=interaction.user, details=f"Leader: {leader.mention}, Map: {map.value}, Flag: {flag}, Members: {', '.join([m.mention for m in members])}")

        confirm_embed = make_embed("__Faction Created__", f"""
🗺️ **Map:** `{map.value}`
🏳️ **Flag:** `{flag}`
🎭 **Role:** {role.mention}
🏠 **Channel:** {channel.mention}
👑 **Leader:** {leader.mention}

👥 **Members:**
{', '.join([m.mention for m in members])}

🎨 **Color:** `{color.name}`
🕓 **Created:** <t:{int(datetime.utcnow().timestamp())}:f>
        """, color=int(color.value.strip("#"), 16))
        await interaction.followup.send(embed=confirm_embed)

async def setup(bot):
    await bot.add_cog(FactionCreate(bot))
