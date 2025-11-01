import discord
from discord import app_commands
from discord.ext import commands

class Factions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color=0x2ECC71):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🎭 Faction Manager 🎭")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    # =======================================
    # /create-faction (single-step)
    # =======================================
    @app_commands.command(name="create-faction", description="Create a faction (role, channel, and permissions).")
    @app_commands.describe(
        name="The faction name.",
        color="Hex color for the role (example: #ff0000)"
    )
    async def create_faction(self, interaction: discord.Interaction, name: str, color: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an **Admin** to use this command!", ephemeral=True)
            return

        guild = interaction.guild

        # Parse color
        try:
            role_color = discord.Color(int(color.strip("#"), 16))
        except ValueError:
            await interaction.response.send_message("⚠️ Invalid color format! Example: `#00FF00`", ephemeral=True)
            return

        # Create role and channel
        role = await guild.create_role(name=name, color=role_color, mentionable=True)
        channel = await guild.create_text_channel(name)

        # Apply permissions
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

        # Confirmation embed
        embed = self.make_embed(
            "__Faction Created__",
            f"""
> ✅ **Channel Created:** {channel.mention}  
> 🎭 **Role Created:** {role.mention}  

**Permissions Granted:**
✓ View Channel  
✓ Send Messages  
✓ Read History  
✓ Add Reactions  
✓ Attach Files  
✓ Embed Links  
✓ Use Slash Commands  

> To delete, use `/delete-faction`.
            """,
            role_color.value
        )

        await interaction.response.send_message(embed=embed)

    # =======================================
    # /delete-faction
    # =======================================
    @app_commands.command(name="delete-faction", description="Delete a faction’s role and channel.")
    @app_commands.describe(
        channel="Select the faction channel to delete.",
        role="Select the faction role to delete."
    )
    async def delete_faction(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin or higher only!", ephemeral=True)
            return

        try:
            await channel.delete()
        except Exception:
            pass

        try:
            await role.delete()
        except Exception:
            pass

        embed = self.make_embed(
            "__Faction Deleted__",
            "> ✅ Faction channel and role have been deleted.",
            0xE74C3C
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Factions(bot))
