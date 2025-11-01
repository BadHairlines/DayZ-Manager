from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import server_vars, FLAGS, MAP_DATA, CUSTOM_EMOJIS
import discord


class Flags(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="flags", description="View the flags for a map")
    @app_commands.describe(selected_map="Select the map to view flags")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def flags(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        map_key = selected_map.value
        guild_id = str(interaction.guild.id)
        guild_data = server_vars.get(guild_id)

        # No setup found yet
        if not guild_data or map_key not in guild_data:
            await interaction.response.send_message(
                f"🚫 {MAP_DATA[map_key]['name']} hasn’t been set up yet! Run `/setup` first.",
                ephemeral=True
            )
            return

        embed = Embed(
            title=f"**———⛳️ {MAP_DATA[map_key]['name'].upper()} FLAGS ⛳️———**",
            color=0x86DC3D
        )
        embed.set_author(name="🚨 Flags Notification 🚨")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()

        # Build flag list
        lines = []
        for flag in FLAGS:
            key = f"{map_key}_{flag}"
            value = guild_data.get(key, "✅")
            emoji = CUSTOM_EMOJIS.get(flag, "")

            # Only show valid emoji format
            if not emoji.startswith("<:"):
                emoji = ""

            if value == "✅":
                display_value = "✅"
            else:
                role_id = guild_data.get(f"{key}_role")
                display_value = f"<@&{role_id}>" if role_id else "❌"

            lines.append(f"{emoji} **• {flag}**: {display_value}")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Flags(bot))
