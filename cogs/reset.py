import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import (
    reset_map_flags, MAP_DATA, db_pool, create_flag_embed, log_action
)
import asyncio


class Reset(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        """Helper to create consistent reset embeds."""
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🧹 Reset Notification 🧹")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        return embed

    async def update_flag_message(self, guild: discord.Guild, guild_id: str, map_key: str):
        """Refresh the live flag message embed after reset."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )
        if not row:
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            return

        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Failed to update flag message after reset: {e}")

    @app_commands.command(
        name="reset",
        description="Reset all flags for a selected map back to ✅."
    )
    @app_commands.describe(selected_map="Select the map to reset (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def reset(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str]
    ):
        """Reset all flags for a map to ✅ and refresh the display."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ This command is for admins ONLY!",
                ephemeral=True
            )
            return

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]

        # 🟡 Step 1: Notify start
        await interaction.response.send_message(
            f"🧹 Resetting **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        try:
            # 🟢 Step 2: Reset flags in DB
            await reset_map_flags(guild_id, map_key)
            await asyncio.sleep(1)

            # 🟢 Step 3: Refresh live message
            await self.update_flag_message(guild, guild_id, map_key)

            # 🟢 Step 4: Build success embed
            embed = discord.Embed(
                title="__RESET COMPLETE__",
                description=(
                    f"✅ **{map_info['name']}** flags successfully reset.\n\n"
                    f"All flags are now marked as ✅ and the live display has been refreshed."
                ),
                color=0x00FF00
            )
            embed.set_image(url=map_info["image"])
            embed.set_author(name="🧹 Reset Notification 🧹")
            embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            embed.timestamp = discord.utils.utcnow()

            await interaction.edit_original_response(content=None, embed=embed)

            # 🪵 Step 5: Log reset action
            await log_action(
                guild,
                map_key,
                f"🧹 **Map Reset:** All flags reset by {interaction.user.mention} "
                f"on **{MAP_DATA[map_key]['name']}**"
            )

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Reset failed for **{map_info['name']}**:\n```{e}```"
            )
            # 🪵 Log failure
            await log_action(
                guild,
                map_key,
                f"❌ **Reset Failed:** Attempt by {interaction.user.mention} on "
                f"**{MAP_DATA[map_key]['name']}** — Error: `{e}`"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reset(bot))
