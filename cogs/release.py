import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, get_flag, release_flag

class Release(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🪧 Release Notification 🪧")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    @app_commands.command(name="release", description="Release a flag back to ✅ for a specific map.")
    @app_commands.describe(
        selected_map="Select the map (Livonia, Chernarus, Sakhal)",
        flag="Select the flag to release"
    )
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def release(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value

        # ✅ Get flag record
        record = await get_flag(guild_id, map_key, flag)
        if not record:
            embed = self.make_embed("**NOT FOUND**", f"The **{flag} Flag** has not been set up yet on **{MAP_DATA[map_key]['name']}**.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if record["status"] == "✅":
            embed = self.make_embed("**ALREADY RELEASED**", f"The **{flag} Flag** is already free on **{MAP_DATA[map_key]['name']}**.", 0xFF0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # ✅ Release flag
        await release_flag(guild_id, map_key, flag)

        embed = self.make_embed(
            "**RELEASED**",
            f"The **{flag} Flag** has been released and is now ✅ available again on **{MAP_DATA[map_key]['name']}**.",
            0x00FF00
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Release(bot))
