import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES
from cogs.utils import reset_map_flags, MAP_DATA, log_action
import asyncio


class Reset(commands.Cog, BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="reset",
        description="Reset all flags for a selected map back to ✅."
    )
    @app_commands.choices(selected_map=MAP_CHOICES)
    @admin_only()
    async def reset(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str]
    ):
        """Reset all flags for a map to ✅ and refresh the display."""
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]

        # 🟡 Notify start
        await interaction.response.send_message(
            f"🧹 Resetting **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        try:
            # 🟢 Step 1: Reset flags in DB
            await reset_map_flags(guild_id, map_key)
            await asyncio.sleep(1)

            # 🟢 Step 2: Refresh live message
            await self.update_flag_message(guild, guild_id, map_key)

            # 🟢 Step 3: Success embed
            embed = self.make_embed(
                "__RESET COMPLETE__",
                f"✅ **{map_info['name']}** flags successfully reset.\n\n"
                f"All flags are now marked as ✅ and the live display has been refreshed.",
                0x2ECC71,
                "🧹",
                "Reset Notification"
            )
            embed.set_image(url=map_info["image"])
            embed.timestamp = discord.utils.utcnow()

            await interaction.edit_original_response(content=None, embed=embed)

            # 🪵 Step 4: Structured log
            await log_action(
                guild,
                map_key,
                title="Map Reset Complete",
                description=(
                    f"🧹 **All flags reset** on **{map_info['name']}** by {interaction.user.mention}.\n"
                    "All flags have been restored to ✅ and the live map view was refreshed."
                ),
                color=0x2ECC71
            )

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Reset failed for **{map_info['name']}**:\n```{e}```"
            )

            await log_action(
                guild,
                map_key,
                title="Map Reset Failed",
                description=(
                    f"❌ **Reset failed** on **{map_info['name']}** by {interaction.user.mention}:\n```{e}```"
                ),
                color=0xE74C3C
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reset(bot))
