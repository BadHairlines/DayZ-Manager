import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import server_vars, save_data, FLAGS, MAP_DATA

class Assign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🪧 Assign Notification 🪧")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    @app_commands.command(name="assign", description="Assign a flag to a role for a specific map.")
    @app_commands.describe(
        selected_map="Select the map (Livonia, Chernarus, Sakhal)",
        flag="Enter the flag name (case-sensitive)",
        role="Select the role to assign the flag to"
    )
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def assign(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value
        guild_data = server_vars.setdefault(guild_id, {})

        # Validate map setup
        if map_key not in guild_data:
            embed = self.make_embed("**NOT SET UP**", f"⚠️ {MAP_DATA[map_key]['name']} hasn’t been set up yet! Run `/setup` first.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if flag not in FLAGS:
            embed = self.make_embed("**DOESN'T EXIST**", f"The **{flag} Flag** does not exist on **{MAP_DATA[map_key]['name']}**.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        flag_key = f"{map_key}_{flag}"
        role_key = f"{flag_key}_role"

        # Check if already assigned
        if guild_data.get(flag_key) == "❌":
            embed = self.make_embed("**ALREADY ASSIGNED**", f"The **{flag} Flag** is already assigned on **{MAP_DATA[map_key]['name']}**.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Assign flag
        guild_data[flag_key] = "❌"
        guild_data[role_key] = role.id
        await save_data()

        embed = self.make_embed("**ASSIGNED**",
            f"The **{flag} Flag** has been marked as ❌ on **{MAP_DATA[map_key]['name']}** and assigned to {role.mention}.",
            0x86DC3D
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Assign(bot))
