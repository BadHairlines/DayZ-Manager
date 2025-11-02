import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs.utils import db_pool  # ✅ shared DB connection

# ==============================
# 🌍 Map Choices
# ==============================
MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]

# 🎨 Color Choices
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


class Factions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==============================
    # 🧱 Ensure Table
    # ==============================
    async def ensure_table(self):
        if db_pool is None:
            print("⚠️ db_pool not initialized — skipping faction table creation.")
            return
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS factions (
                    id SERIAL PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    map TEXT NOT NULL,
                    faction_name TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    leader_id TEXT NOT NULL,
                    member_ids TEXT[],
                    color TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (guild_id, faction_name)
                );
            """)

    # ==============================
    # 🧩 Utility
    # ==============================
    def make_embed(self, title, desc, color=0x2ECC71):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🎭 Faction Manager")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        return embed

    # =======================================
    # 🏗️ /create-faction
    # =======================================
    @app_commands.command(name="create-faction", description="Create a faction with a role, channel, and members.")
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    @app_commands.describe(
        name="Faction name",
        map="Select the map this faction belongs to",
        color="Faction color",
        leader="Faction leader",
        member1="Faction member #1",
        member2="Faction member #2",
        member3="Faction member #3"
    )
    async def create_faction(
        self,
        interaction: discord.Interaction,
        name: str,
        map: app_commands.Choice[str],
        color: app_commands.Choice[str],
        leader: discord.Member,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None
    ):
        await interaction.response.defer(thinking=True, ephemeral=False)
        await self.ensure_table()

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ You must be an **Admin** to use this command.", ephemeral=True)
            return

        guild = interaction.guild
        role_color = discord.Color(int(color.value.strip("#"), 16))

        # Prevent duplicates
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), name
            )
        if existing:
            await interaction.followup.send(
                f"⚠️ Faction **{name}** already exists on {existing['map']}!",
                ephemeral=True
            )
            return

        # Category
        category_name = f"{map.value} Factions Hub"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            print(f"📁 Created category: {category_name}")

        # Role
        role = await guild.create_role(name=name, color=role_color, mentionable=True)
        divider = discord.utils.get(guild.roles, name="────────── Factions ──────────")
        if divider:
            try:
                await role.edit(position=divider.position - 1)
            except Exception:
                pass

        # Channel
        channel = await guild.create_text_channel(
            name.lower().replace(" ", "-"),
            category=category,
            topic=f"Private HQ for the {name} faction on {map.value}."
        )
        await channel.set_permissions(role, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.default_role, read_messages=False)

        # Assign roles
        members = [m for m in [leader, member1, member2, member3] if m]
        for m in members:
            try:
                await m.add_roles(role)
            except Exception as e:
                print(f"⚠️ Could not assign role to {m}: {e}")

        # Save DB
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO factions (guild_id, map, faction_name, role_id, channel_id, leader_id, member_ids, color)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """, str(guild.id), map.value, name, str(role.id), str(channel.id),
                str(leader.id), [str(m.id) for m in members], color.value)

        members_txt = "\n".join([m.mention for m in members])
        embed = self.make_embed(
            "__Faction Created__",
            f"""
> 🗺️ **Map:** `{map.value}`
> 🎭 **Role:** {role.mention}
> 🏠 **Channel:** {channel.mention}
> 👑 **Leader:** {leader.mention}
> 👥 **Members:**\n{members_txt}
> 🎨 **Color:** `{color.name}`
> 🕓 **Created:** <t:{int(datetime.utcnow().timestamp())}:f>
            """,
            role_color.value
        )
        await interaction.followup.send(embed=embed)

    # =======================================
    # 🗑️ /delete-faction
    # =======================================
    @app_commands.command(name="delete-faction", description="Delete a faction and remove from DB.")
    @app_commands.describe(name="Name of the faction to delete")
    async def delete_faction(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Admin only!", ephemeral=True)
            return

        await self.ensure_table()
        guild = interaction.guild

        async with db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), name
            )
        if not faction:
            await interaction.followup.send(f"❌ Faction `{name}` not found.", ephemeral=True)
            return

        # Try deleting
        try:
            if (ch := guild.get_channel(int(faction["channel_id"]))):
                await ch.delete()
            if (r := guild.get_role(int(faction["role_id"]))):
                await r.delete()
        except Exception as e:
            print(f"⚠️ Failed to delete role/channel: {e}")

        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2",
                               str(guild.id), name)

        await interaction.followup.send(
            embed=self.make_embed("✅ Faction Deleted", f"Faction **{name}** removed successfully.", 0xE74C3C),
            ephemeral=True
        )

    # =======================================
    # ➕ /add-member
    # =======================================
    @app_commands.command(name="add-member", description="Add a member to a faction.")
    async def add_member(self, interaction: discord.Interaction, faction_name: str, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only admins can add members.", ephemeral=True)
            return

        await self.ensure_table()
        guild = interaction.guild
        async with db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), faction_name
            )
        if not faction:
            await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)
            return

        members = faction["member_ids"] or []
        if str(member.id) in members:
            await interaction.followup.send(f"⚠️ {member.mention} is already in `{faction_name}`.", ephemeral=True)
            return

        members.append(str(member.id))
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

        if (role := guild.get_role(int(faction["role_id"]))):
            await member.add_roles(role)

        embed = self.make_embed("✅ Member Added", f"👥 {member.mention} added to **{faction_name}**.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # =======================================
    # ➖ /remove-member
    # =======================================
    @app_commands.command(name="remove-member", description="Remove a member from a faction.")
    async def remove_member(self, interaction: discord.Interaction, faction_name: str, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only admins can remove members.", ephemeral=True)
            return

        await self.ensure_table()
        guild = interaction.guild
        async with db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), faction_name
            )
        if not faction:
            await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)
            return

        members = faction["member_ids"] or []
        if str(member.id) not in members:
            await interaction.followup.send(f"⚠️ {member.mention} is not in `{faction_name}`.", ephemeral=True)
            return

        members.remove(str(member.id))
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

        if (role := guild.get_role(int(faction["role_id"]))):
            await member.remove_roles(role)

        embed = self.make_embed("✅ Member Removed", f"👋 {member.mention} removed from **{faction_name}**.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Factions(bot))
