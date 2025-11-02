import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES
from cogs.utils import FLAGS, MAP_DATA, release_flag, log_action


class Release(commands.Cog, BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete flag names."""
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    @app_commands.command(
        name="release",
        description="Release a flag back to ✅ for a specific map."
    )
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    @admin_only()
    async def release(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str
    ):
        """Releases a claimed flag back to ✅ available."""
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_name = MAP_DATA[map_key]["name"]

        # ✅ Release flag in DB
        await release_flag(guild_id, map_key, flag)

        # ✅ Confirmation embed
        embed = self.make_embed(
            "**FLAG RELEASED**",
            f"✅ The **{flag}** flag has been released and is now available again on **{map_name}**.",
            0x2ECC71,
            "🏳️",
            "Release Notification"
        )
        await interaction.response.send_message(embed=embed)

        # 🔁 Update the live flag message
        await self.update_flag_message(guild, guild_id, map_key)

        # 🪵 Structured log entry
        await log_action(
            guild,
            map_key,
            title="Flag Released",
            description=f"🏳️ **{flag}** released by {interaction.user.mention} on **{map_name}**.",
            color=0x2ECC71
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Release(bot))
