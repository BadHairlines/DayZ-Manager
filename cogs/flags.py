import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, CUSTOM_EMOJIS, get_all_flags


class Flags(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="flags", description="View all flags and their status for a specific map.")
    @app_commands.describe(selected_map="Select the map to view flags")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def flags(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        guild_id = str(interaction.guild.id)
        map_key = selected_map.value

        # Fetch all flag records for this guild and map
        records = await get_all_flags(guild_id, map_key)
        db_flags = {r["flag"]: r for r in records} if records else {}

        # If there’s nothing in DB yet, suggest setup
        if not records:
            await interaction.response.send_message(
                f"🚫 {MAP_DATA[map_key]['name']} hasn’t been set up yet or has no data. Run `/setup` first.",
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

        lines = []
        for flag in FLAGS:
            data = db_flags.get(flag)
            status = data["status"] if data else "✅"
            role_id = data["role_id"] if data and data["role_id"] else None
            emoji = CUSTOM_EMOJIS.get(flag, "")

            # Only show valid emoji format
            if not emoji.startswith("<:"):
                emoji = ""

            display_value = "✅" if status == "✅" else (f"<@&{role_id}>" if role_id else "❌")
            lines.append(f"{emoji} **• {flag}**: {display_value}")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Flags(bot))
