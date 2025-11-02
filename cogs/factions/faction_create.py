import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs import utils
from .faction_utils import ensure_faction_table, make_embed

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal")
]
COLOR_CHOICES = [
    app_commands.Choice(name="Red", value="#FF0000"),
    app_commands.Choice(name="Orange", value="#FFA500"),
    app_commands.Choice(name="Yellow", value="#FFFF00"),
    app_commands.Choice(name="Green", value="#00FF00"),
    app_commands.Choice(name="Blue", value="#0000FF"),
    app_commands.Choice(name="Purple", value="#800080"),
    app_commands.Choice(name="Pink", value="#FF69B4"),
    app_commands.Choice(name="Cyan", value="#00FFFF"),
    app_commands.Choice(name="White", value="#FFFFFF"),
    app_commands.Choice(name="Black", value="#000000"),
    app_commands.Choice(name="Grey", value="#808080"),
    app_commands.Choice(name="Brown", value="#8B4513")
]

class FactionCreate(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def flag_autocomplete(self, interaction:discord.Interaction, current:str):
        return [app_commands.Choice(name=f, value=f) for f in utils.FLAGS if current.lower() in f.lower()][:25]

    @app_commands.command(name="create-faction", description="Create a faction, assign a flag, and set up its role and HQ.")
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def create_faction(self, interaction:discord.Interaction, name:str, map:app_commands.Choice[str], flag:str, color:app_commands.Choice[str], leader:discord.Member, member1:discord.Member|None=None, member2:discord.Member|None=None, member3:discord.Member|None=None):
        await interaction.response.defer(thinking=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("Only admins can create factions.", ephemeral=True)
        if utils.db_pool is None: raise RuntimeError("Database not initialized.")
        await ensure_faction_table()
        guild, guild_id, map_key = interaction.guild, str(interaction.guild.id), map.value
        role_color = discord.Color(int(color.value.strip("#"),16))
        async with utils.db_pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2", guild_id, name)
        if existing: return await interaction.followup.send(f"Faction {name} already exists on {existing['map']}.", ephemeral=True)
        flags = await utils.get_all_flags(guild_id, map_key)
        flag_data = next((f for f in flags if f["flag"].lower()==flag.lower()), None)
        if not flag_data: return await interaction.followup.send(f"Flag {flag} does not exist on {map_key}.", ephemeral=True)
        if flag_data["status"]=="❌": return await interaction.followup.send(f"Flag {flag} already owned by <@&{flag_data['role_id']}>.", ephemeral=True)
        category = discord.utils.get(guild.categories, name=f"{map.value} Factions Hub") or await guild.create_category(f"{map.value} Factions Hub")
        role = await guild.create_role(name=name, color=role_color, mentionable=True)
        divider = discord.utils.get(guild.roles, name="────────── Factions ──────────")
        if divider: 
            try: await role.edit(position=divider.position-1)
            except Exception: pass
        channel = await guild.create_text_channel(name.lower().replace(" ","-"), category=category, topic=f"Private HQ for {name} faction on {map.value}.")
        await channel.set_permissions(role, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.default_role, read_messages=False)
        members = [m for m in [leader, member1, member2, member3] if m]
        for m in members:
            try: await m.add_roles(role)
            except Exception: pass
        async with utils.db_pool.acquire() as conn:
            await conn.execute("INSERT INTO factions (guild_id,map,faction_name,role_id,channel_id,leader_id,member_ids,color) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",guild_id,map.value,name,str(role.id),str(channel.id),str(leader.id),[str(m.id) for m in members],color.value)
        await utils.set_flag(guild_id,map_key,flag,"❌",str(role.id))
        try:
            embed = await utils.create_flag_embed(guild_id,map_key)
            async with utils.db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT channel_id,message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",guild_id,map_key)
            if row:
                ch=guild.get_channel(int(row["channel_id"]))
                msg=await ch.fetch_message(int(row["message_id"]))
                await msg.edit(embed=embed)
        except Exception: pass
        members_list = "\n".join([m.mention for m in members if m.id!=leader.id]) or "*No members listed*"
        welcome_embed = discord.Embed(title=f"Welcome to {name}!", description=(f"Welcome to your {map.value} HQ, {role.mention}.\n\nLeader: {leader.mention}\nMembers:\n{members_list}\n\nFlag: {flag}\nColor: {color.name}\nCreated: <t:{int(datetime.utcnow().timestamp())}:f>"), color=role_color)
        welcome_embed.set_footer(text=f"{map.value} • Faction HQ", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        msg = await channel.send(embed=welcome_embed)
        try: await msg.pin()
        except Exception: pass
        await utils.log_faction_action(guild, action="Faction Created + Flag Claimed", faction_name=name, user=interaction.user, details=f"Leader: {leader.mention}, Map: {map.value}, Flag: {flag}, Members: {', '.join([m.mention for m in members])}")
        confirm_embed = make_embed("Faction Created", f"Map: `{map.value}`\nFlag: `{flag}`\nRole: {role.mention}\nChannel: {channel.mention}\nLeader: {leader.mention}\nMembers: {', '.join([m.mention for m in members])}\nColor: `{color.name}`\nCreated: <t:{int(datetime.utcnow().timestamp())}:f>", color=int(color.value.strip('#'),16))
        await interaction.followup.send(embed=confirm_embed)

async def setup(bot): await bot.add_cog(FactionCreate(bot))
