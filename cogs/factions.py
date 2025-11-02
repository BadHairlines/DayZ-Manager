import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs.utils import db_pool  # ✅ use shared DB connection

# ==============================
# 🌍 Console Maps
# ==============================
MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]

# 🎨 Color choices
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
    # 🧱 Database Setup
    # ==============================
    async def ensure_table(self):
        """Safely ensure the factions table exists."""
        if db_pool is None:
            print("⚠️ Warning: db_pool not initialized — skipping table creation.")
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
    # 📦 Utility Embed Builder
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
    # /create-faction
    # =======================================
    @app_commands.command(
        name="create-faction",
        description="Create a faction (role, channel, and assign members)."
    )
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    @app_commands.describe(
        name="Faction name",
        map="Select which map this faction belongs to",
        color="Select faction color",
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
        await interaction.response.defer(thinking=True)
        await self.ensure_table()

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ You must be an **Admin** to use this command!", ephemeral=True)
            return

        guild = interaction.guild
        role_color = discord.Color(int(color.value.strip("#"), 16))

        # 🧩 Check for duplicates
        if db_pool:
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

        # 🗂️ Category setup
        category_name = f"{map.value} Factions Hub"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            print(f"📁 Created category: {category_name}")

        # 🎭 Create faction role and channel
        role = await guild.create_role(name=name, color=role_color, mentionable=True)
        divider = discord.utils.get(guild.roles, name="────────── Factions ──────────")
        if divider:
            try:
                await role.edit(position=divider.position - 1)
            except Exception:
                pass

        channel_name = name.lower().replace(" ", "-")
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            topic=f"Private HQ for the {name} faction on {map.value}."
        )

        # 🔐 Permissions
        await channel.set_permissions(role,
            read_messages=True,
            send_messages=True,
            read_message_history=True,
            add_reactions=True,
            attach_files=True,
            embed_links=True,
            use_application_commands=True
        )
        await channel.set_permissions(guild.default_role, read_messages=False)

        # 👥 Assign members
        members = [m for m in [leader, member1, member2, member3] if m]
        for member in members:
            try:
                await member.add_roles(role)
            except Exception as e:
                print(f"⚠️ Failed to assign role to {member}: {e}")

        # 💾 Save to DB
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO factions (guild_id, map, faction_name, role_id, channel_id, leader_id, member_ids, color)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, str(guild.id), map.value, name, str(role.id), str(channel.id),
                    str(leader.id), [str(m.id) for m in members], color.value)

        # 🏠 Welcome Embed
        members_list = "\n".join([m.mention for m in members]) if len(members) > 1 else "*No members listed*"
        welcome_embed = discord.Embed(
            title=f"🎖️ Welcome to {name}",
            description=(
                f"Welcome to your **{map.value} HQ**, {role.mention}!\n\n"
                f"👑 **Leader:** {leader.mention}\n"
                f"👥 **Members:**\n{members_list}\n\n"
                f"**Faction Color:** `{color.name}`\n"
                "This is your private faction base for communication and coordination. ⚔️"
            ),
            color=role_color
        )
        welcome_embed.set_footer(
            text=f"{map.value} • Faction HQ",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        await channel.send(embed=welcome_embed)

        # ✅ Confirmation Embed
        admin_members_list = "\n".join([m.mention for m in members]) if len(members) > 1 else "*No members*"
        embed = self.make_embed(
            "__Faction Created__",
            f"""
> 🗺️ **Map:** `{map.value}`  
> 🏠 **Channel:** {channel.mention}  
> 🎭 **Role:** {role.mention}  
> 🎨 **Color:** `{color.name}`  
> 👑 **Leader:** {leader.mention}  
> 👥 **Members:**\n{admin_members_list}  
> 🕓 **Created:** <t:{int(datetime.utcnow().timestamp())}:f>
            """,
            role_color.value
        )
        await interaction.followup.send(embed=embed)

    # =======================================
    # /delete-faction
    # =======================================
    @app_commands.command(name="delete-faction", description="Delete a faction’s role, channel, and DB record.")
    @app_commands.describe(name="Faction name to delete")
    async def delete_faction(self, interaction: discord.Interaction, name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin or higher only!", ephemeral=True)
            return

        await self.ensure_table()
        guild = interaction.guild

        faction = None
        if db_pool:
            async with db_pool.acquire() as conn:
                faction = await conn.fetchrow(
                    "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                    str(guild.id), name
                )

        if not faction:
            await interaction.response.send_message(f"❌ No faction named `{name}` found.", ephemeral=True)
            return

        view = discord.ui.View()

        async def confirm(inter: discord.Interaction):
            await inter.response.defer()

            channel = guild.get_channel(int(faction["channel_id"]))
            role = guild.get_role(int(faction["role_id"]))

            try:
                if channel:
                    await channel.delete()
                if role:
                    await role.delete()
            except Exception:
                pass

            if db_pool:
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2",
                        str(guild.id), name
                    )

            embed = self.make_embed(
                "__Faction Deleted__",
                f"> ✅ Faction **{name}** removed from Discord and database.",
                0xE74C3C
            )
            await inter.followup.send(embed=embed, ephemeral=True)
            view.stop()

        async def cancel(inter: discord.Interaction):
            await inter.response.send_message("❌ Deletion cancelled.", ephemeral=True)
            view.stop()

        confirm_btn = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger)
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        confirm_btn.callback = confirm
        cancel_btn.callback = cancel
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)

        await interaction.response.send_message(
            f"⚠️ Are you sure you want to delete faction **{name}**?",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Factions(bot))
