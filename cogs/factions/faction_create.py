import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs.utils import db_pool
from .faction_utils import ensure_faction_table, make_embed

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]

COLOR_CHOICES = [
    app_commands.Choice(name="Red ❤️", value="#FF0000"),
    app_commands.Choice(name="Blue 💙", value="#0000FF"),
    app_commands.Choice(name="Green 💚", value="#00FF00"),
    app_commands.Choice(name="Black 🖤", value="#000000"),
]

class FactionCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create-faction", description="Create a faction with a role, channel, and members.")
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    async def create_faction(self, interaction, name: str, map, color, leader: discord.Member,
                             member1: discord.Member | None = None,
                             member2: discord.Member | None = None,
                             member3: discord.Member | None = None):
        await interaction.response.defer(thinking=True)
        await ensure_faction_table()

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admin only.", ephemeral=True)

        guild = interaction.guild
        role_color = discord.Color(int(color.value.strip("#"), 16))
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2", str(guild.id), name)
        if existing:
            return await interaction.followup.send(f"⚠️ Faction `{name}` already exists!", ephemeral=True)

        category_name = f"{map.value} Factions Hub"
        category = discord.utils.get(guild.categories, name=category_name) or await guild.create_category(category_name)
        role = await guild.create_role(name=name, color=role_color, mentionable=True)
        channel = await guild.create_text_channel(name.lower().replace(" ", "-"), category=category, topic=f"Private HQ for {name}")
        await channel.set_permissions(role, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.default_role, read_messages=False)

        members = [m for m in [leader, member1, member2, member3] if m]
        for m in members:
            await m.add_roles(role)

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO factions (guild_id, map, faction_name, role_id, channel_id, leader_id, member_ids, color)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """, str(guild.id), map.value, name, str(role.id), str(channel.id), str(leader.id), [str(m.id) for m in members], color.value)

        members_list = "\n".join([m.mention for m in members if m.id != leader.id]) or "*No members listed*"
        welcome_embed = discord.Embed(
            title=f"🎖️ Welcome to {name}!",
            description=(
                f"Welcome to your **{map.value} HQ**, {role.mention}! ⚔️\n\n"
                f"👑 **Leader:** {leader.mention}\n"
                f"👥 **Members:**\n{members_list}\n\n"
                f"🎨 **Color:** `{color.name}`\n"
                f"🕓 **Created:** <t:{int(datetime.utcnow().timestamp())}:f>"
            ),
            color=role_color
        )
        await channel.send(embed=welcome_embed)
        await interaction.followup.send(embed=make_embed("__Faction Created__", f"Faction **{name}** created successfully!"))

async def setup(bot):
    await bot.add_cog(FactionCreate(bot))
