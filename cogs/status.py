import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs.utils import FLAGS, MAP_DATA, get_all_flags, log_action, db_pool


class Status(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="status",
        description="View a summary of flag statuses for a specific map, or all maps if none selected."
    )
    @app_commands.describe(selected_map="Select a map to view its status, or leave empty for full overview.")
    async def status(
        self,
        interaction: discord.Interaction,
        selected_map: str | None = None
    ):
        """Displays flag ownership summary for one map, or an overview of all maps."""
        guild = interaction.guild
        guild_id = str(guild.id)
        await interaction.response.defer(thinking=True)

        # ==========================
        # 🧭 If specific map selected
        # ==========================
        if selected_map:
            map_key = selected_map.lower()
            if map_key not in MAP_DATA:
                await interaction.followup.send(f"❌ Unknown map: `{selected_map}`", ephemeral=True)
                return

            map_info = MAP_DATA[map_key]
            rows = await get_all_flags(guild_id, map_key)
            if not rows:
                await interaction.followup.send(
                    f"🚫 {map_info['name']} hasn’t been set up yet. Run `/setup` first.",
                    ephemeral=True
                )
                await log_action(
                    guild,
                    map_key,
                    title="Status Check Failed",
                    description=f"🚫 {interaction.user.mention} tried to check **{map_info['name']}**, but it’s not set up.",
                    color=0xE74C3C
                )
                return

            total_flags = len(FLAGS)
            taken_flags = sum(1 for r in rows if r["status"] == "❌")
            available_flags = total_flags - taken_flags

            owners = [
                f"• {record['flag']} → <@&{record['role_id']}>"
                for record in rows if record["status"] == "❌" and record["role_id"]
            ]
            owners_text = "\n".join(owners) if owners else "_No claimed flags currently._"

            embed = discord.Embed(
                title=f"**———📊 {map_info['name'].upper()} STATUS 📊———**",
                color=0x3498DB
            )
            embed.set_author(name="📍 Flag Status Report")
            embed.set_thumbnail(url=map_info["image"])
            embed.add_field(name="✅ Available Flags", value=f"**{available_flags}/{total_flags}**", inline=True)
            embed.add_field(name="❌ Claimed Flags", value=f"**{taken_flags}/{total_flags}**", inline=True)
            embed.add_field(
                name="🧭 Last Updated",
                value=f"<t:{int(datetime.utcnow().timestamp())}:R>",
                inline=False
            )
            embed.add_field(name="🏷️ Claimed By", value=owners_text, inline=False)
            embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
            embed.timestamp = discord.utils.utcnow()

            await interaction.followup.send(embed=embed)
            await log_action(
                guild,
                map_key,
                title="Status Viewed",
                description=(f"📊 {interaction.user.mention} viewed **{map_info['name']}** status. "
                             f"✅ {available_flags}/{total_flags} available, ❌ {taken_flags}/{total_flags} claimed."),
                color=0x3498DB
            )
            return

        # ==========================
        # 🗺️ Otherwise, show overview of all maps
        # ==========================
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT map FROM flag_messages WHERE guild_id=$1;", guild_id)

        if not rows:
            await interaction.followup.send("🚫 No maps have been set up yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"**———🌍 FLAG OVERVIEW ({guild.name}) 🌍———**",
            description="📊 Summary of all map flag statuses.",
            color=0x00BFFF
        )
        embed.set_author(name="📍 Map Overview Dashboard")

        for row in rows:
            map_key = row["map"]
            if map_key not in MAP_DATA:
                continue

            flags = await get_all_flags(guild_id, map_key)
            total = len(FLAGS)
            taken = sum(1 for f in flags if f["status"] == "❌")
            available = total - taken

            embed.add_field(
                name=f"🗺️ {MAP_DATA[map_key]['name']}",
                value=f"✅ **{available}/{total}** available\n❌ **{taken}/{total}** claimed",
                inline=False
            )

        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed)

        # ✅ Optional: log overview usage
        for row in rows:
            await log_action(
                guild,
                row["map"],
                title="Overview Viewed",
                description=f"🌍 {interaction.user.mention} viewed full flag overview for **{guild.name}**.",
                color=0x1ABC9C
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))
