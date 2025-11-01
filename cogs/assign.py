import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, set_flag, get_all_flags

class Assign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🪧 Assign Notification 🪧")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    @app_commands.command(name="assign", description="Assign a flag to a role for a specific map.")
    @app_commands.describe(
        selected_map="Select the map (Livonia, Chernarus, Sakhal)",
        flag="Select the flag to assign",
        role="Select the role to assign the flag to"
    )
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def assign(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value

        # ✅ Check if role already owns a flag on this map
        existing_flags = await get_all_flags(guild_id, map_key)
        for record in existing_flags:
            if record["role_id"] == str(role.id):
                embed = self.make_embed(
                    "**ALREADY HAS A FLAG**",
                    f"{role.mention} already owns the **{record['flag']}** flag on **{MAP_DATA[map_key]['name']}**.",
                    0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        # ✅ Check if flag already assigned
        for record in existing_flags:
            if record["flag"] == flag and record["status"] == "❌":
                embed = self.make_embed(
                    "**ALREADY ASSIGNED**",
                    f"The **{flag} Flag** is already assigned on **{MAP_DATA[map_key]['name']}**.",
                    0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        # ✅ Assign the flag in the database
        await set_flag(guild_id, map_key, flag, "❌", str(role.id))

        embed = self.make_embed(
            "**ASSIGNED**",
            f"The **{flag} Flag** has been marked as ❌ on **{MAP_DATA[map_key]['name']}** and assigned to {role.mention}.",
            0x86DC3D
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Assign(bot))
