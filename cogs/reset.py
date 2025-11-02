import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs import utils


class Reset(commands.Cog, BaseCog):
    """Reset all flags and faction claims for a specific map."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="reset",
        description="Reset all flags on a map back to ✅ and clear any faction claims."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    async def reset(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str]
    ):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = normalize_map(selected_map)
        map_name = utils.MAP_DATA[map_key]["name"]

        # ✅ Ensure DB is ready
        if utils.db_pool is None:
            return await interaction.followup.send("❌ Database not initialized. Please restart the bot.", ephemeral=True)

        # 🟡 Start message
        await interaction.followup.send(
            f"🧹 Resetting **{map_name}** flags... please wait ⏳",
            ephemeral=True
        )

        try:
            # 🔹 Step 1: Reset flags in DB (and clear faction claims)
            await utils.reset_map_flags(guild_id, map_key)
            await asyncio.sleep(1)

            # 🔹 Step 2: Update live flag embed
            try:
                await self.update_flag_message(guild, guild_id, map_key)
            except Exception as e:
                print(f"⚠️ Failed to update flag embed during reset: {e}")

            # 🔹 Step 3: Send confirmation embed
            embed = self.make_embed(
                title="__RESET COMPLETE__",
                desc=(
                    f"✅ **{map_name}** flags successfully reset.\n\n"
                    f"🏳️ All flags are now available (✅)\n"
                    f"🔄 All faction `claimed_flag` values cleared.\n"
                    f"📜 Live display updated automatically."
                ),
                color=0x2ECC71,
                author_icon="🧹",
                author_name="Map Reset"
            )
            embed.set_image(url=utils.MAP_DATA[map_key]["image"])
            embed.timestamp = discord.utils.utcnow()
            await interaction.edit_original_response(content=None, embed=embed)

            # 🔹 Step 4: Log in map-specific logs
            await utils.log_action(
                guild,
                map_key,
                title="Map Reset Complete",
                description=(
                    f"🧹 **{map_name}** reset by {interaction.user.mention}.\n"
                    "All flags restored to ✅ and all faction claims cleared."
                ),
                color=0x2ECC71
            )

            # 🔹 Step 5: Log in faction-logs channel
            await utils.log_faction_action(
                guild,
                action="Map Reset",
                faction_name=None,
                user=interaction.user,
                details=f"Reset all faction flag claims on map `{map_name}`."
            )

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Reset failed for **{map_name}**:\n```{e}```"
            )
            await utils.log_action(
                guild,
                map_key,
                title="Map Reset Failed",
                description=f"❌ Reset failed for **{map_name}** by {interaction.user.mention}:\n```{e}```",
                color=0xE74C3C
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reset(bot))
