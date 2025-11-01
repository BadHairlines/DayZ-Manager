import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, set_flag
import asyncio


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup a map and initialize all flags in the database.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(selected_map="Select the map to setup (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def setup(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        guild_id = str(interaction.guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]

        # ✅ Send initial progress message
        await interaction.response.send_message(
            f"⚙️ Setting up **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        # ✅ Perform setup
        try:
            for flag in FLAGS:
                await set_flag(guild_id, map_key, flag, "✅", None)
                await asyncio.sleep(0.05)  # helps prevent async pool congestion

            # ✅ Prepare success embed
            embed = Embed(
                title="__SETUP COMPLETE__",
                description=f"✅ **{map_info['name']}** setup finished successfully.\n\nAll flags have been initialized in the database.",
                color=0x00FF00
            )
            embed.set_image(url=map_info["image"])
            embed.set_author(name="🚨 Setup Notification 🚨")
            embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            embed.timestamp = discord.utils.utcnow()

            await interaction.edit_original_response(content=None, embed=embed)

        except Exception as e:
            # ✅ If an error happens mid-setup, update message instead of new response
            await interaction.edit_original_response(
                content=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```"
            )

    @setup.error
    async def setup_error(self, interaction: Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "🚫 This command is for admins ONLY!", ephemeral=True
            )
        else:
            # ✅ use followup.send since response may already exist
            await interaction.followup.send(
                f"❌ An unexpected error occurred:\n```{error}```",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
