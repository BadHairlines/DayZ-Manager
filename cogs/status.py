import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import (
    FLAGS, MAP_DATA, get_all_flags, db_pool, create_flag_embed, log_action
)
from datetime import datetime


class Status(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        """Helper to keep embeds consistent."""
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="📊 Status Overview 📊")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(
        name="status",
        description="View a summary of all flag statuses for a selected map."
    )
    @app_commands.describe(selected_map="Select the map to view flag status for")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def status(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str]
    ):
        """Displays flag ownership summary for a map."""
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]

        await interaction.response.defer(thinking=True)

        # ✅ Fetch all flags from the DB
        rows = await get_all_flags(guild_id, map_key)
        if not rows:
            await interaction.followup.send(
                f"🚫 {map_info['name']} hasn’t been set up yet. Run `/setup` first.",
                ephemeral=True
            )

            # 🪵 Log failed status check
            await log_action(
                guild,
                map_key,
                title="Status Check Failed",
                description=f"🚫 {interaction.user.mention} tried to check **{map_info['name']}**, but it hasn’t been set up yet.",
                color=0xE74C3C
            )
            return

        # 🧮 Count totals
        total_flags = len(FLAGS)
        taken_flags = sum(1 for r in rows if r["status"] == "❌")
        available_flags = total_flags - taken_flags

        # 🏷️ List all ownerships
        owners = []
        for record in rows:
            if record["status"] == "❌" and record["role_id"]:
                owners.append(f"• {record['flag']} → <@&{record['role_id']}>")

        owners_text = "\n".join(owners) if owners else "_No claimed flags currently._"

        # 📊 Build the status embed
        embed = discord.Embed(
            title=f"**———📊 {map_info['name'].upper()} STATUS 📊———**",
            color=0x3498DB
        )
        embed.set_author(name="📍 Flag Status Report")
        embed.set_thumbnail(url=map_info["image"])
        embed.add_field(name="✅ Available Flags", value=f"**{available_flags}/{total_flags}**", inline=True)
        embed.add_field(name="❌ Claimed Flags", value=f"**{taken_flags}/{total_flags}**", inline=True)
        embed.add_field(name="🧭 Last Updated", value=f"<t:{int(datetime.utcnow().timestamp())}:R>", inline=False)
        embed.add_field(name="🏷️ Claimed By", value=owners_text, inline=False)
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await interaction.followup.send(embed=embed)

        # 🪵 Log successful status view
        await log_action(
            guild,
            map_key,
            title="Status Viewed",
            description=(
                f"📊 {interaction.user.mention} viewed the **status report** for **{map_info['name']}**.\n"
                f"✅ Available: **{available_flags}/{total_flags}**, ❌ Claimed: **{taken_flags}/{total_flags}**."
            ),
            color=0x3498DB
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))
