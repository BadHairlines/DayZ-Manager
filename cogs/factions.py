import discord
from discord import app_commands
from discord.ext import commands

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

    def make_embed(self, title, desc, color=0x2ECC71):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🎭 Faction Manager")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    # =======================================
    # /create-faction (with leader + members)
    # =======================================
    @app_commands.command(name="create-faction", description="Create a faction (role, channel, and assign members).")
    @app_commands.describe(
        name="Faction name",
        map="Select which map this faction belongs to",
        leader="Faction leader",
        member1="Faction member #1",
        member2="Faction member #2",
        member3="Faction member #3"
    )
    @app_commands.choices(color=COLOR_CHOICES, map=MAP_CHOICES)
    async def create_faction(
        self,
        interaction: discord.Interaction,
        name: str,
        color: app_commands.Choice[str],
        map: app_commands.Choice[str],
        leader: discord.Member,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None
    ):
        # ✅ Defer early to prevent timeout
        await interaction.response.defer(thinking=True)

        # Admin check
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ You must be an **Admin** to use this command!", ephemeral=True)
            return

        guild = interaction.guild
        color_hex = color.value
        role_color = discord.Color(int(color_hex.strip("#"), 16))

        # 🗂️ Category setup (create if not exists)
        category_name = f"{map.value} Factions Hub"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            print(f"📁 Created category: {category_name}")

        # 🎭 Create faction role + private channel
        role = await guild.create_role(name=name, color=role_color, mentionable=True)
        channel_name = name.lower().replace(" ", "-")
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            topic=f"Private HQ for the {name} faction on {map.value}."
        )

        # 🔐 Set permissions
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

        # 🏠 Faction welcome message
        members_list = "\n".join([m.mention for m in members]) if len(members) > 1 else "*No members listed*"
        welcome_embed = discord.Embed(
            title=f"🎖️ Welcome to {name}",
            description=(
                f"Welcome to your **{map.value} HQ**, {role.mention}!\n\n"
                f"👑 **Leader:** {leader.mention}\n"
                f"👥 **Members:**\n{members_list}\n\n"
                "This is your private faction base for communication and coordination.\n"
                "Stay active to maintain your faction’s presence on the server! ⚔️\n\n"
                f"**Faction Color:** `{color.name}`"
            ),
            color=role_color
        )
        welcome_embed.set_footer(text=f"{map.value} • Faction HQ", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        await channel.send(embed=welcome_embed)

        # ✅ Confirmation to Admin
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

**Permissions Granted:**
✅ View Channel  
✅ Send Messages  
✅ Read History  
✅ Attach Files  
✅ Embed Links  
✅ Use Slash Commands  

> To delete later, use `/delete-faction`.
            """,
            role_color.value
        )

        await interaction.followup.send(embed=embed)

    # =======================================
    # /delete-faction
    # =======================================
    @app_commands.command(name="delete-faction", description="Delete a faction’s role and channel.")
    @app_commands.describe(channel="Faction channel to delete.", role="Faction role to delete.")
    async def delete_faction(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin or higher only!", ephemeral=True)
            return

        view = discord.ui.View()

        async def confirm(inter: discord.Interaction):
            await inter.response.defer()
            try:
                await channel.delete()
            except Exception:
                pass
            try:
                await role.delete()
            except Exception:
                pass

            embed = self.make_embed("__Faction Deleted__", "> ✅ Faction channel and role deleted.", 0xE74C3C)
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
            f"⚠️ Are you sure you want to delete {role.mention} and {channel.mention}?",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Factions(bot))
