import discord
from discord import app_commands
from discord.ext import commands

from dayz_manager.cogs.helpers.base_cog import BaseCog
from dayz_manager.cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from dayz_manager.cogs.utils.database import db_pool
from dayz_manager.cogs.utils.logging import log_action, log_faction_action
from dayz_manager.config import FLAGS as ALL_FLAGS

class Release(commands.Cog, BaseCog):
    """Release a flag (make it available again)."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="release", description="Release a claimed flag and make it available again.")
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(selected_map="Select the map containing the flag to release", flag="Enter the flag name to release (e.g. Wolf, NAPA, APA)")
    async def release(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = normalize_map(selected_map)

        if db_pool is None:
            return await interaction.followup.send("❌ Database not initialized. Please restart the bot.", ephemeral=True)

        if flag not in ALL_FLAGS:
            return await interaction.followup.send(f"🚫 Invalid flag name. Must be one of:\n`{', '.join(ALL_FLAGS)}`", ephemeral=True)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM flags WHERE guild_id=$1 AND map=$2 AND flag=$3;", guild_id, map_key, flag)

        if not row or row["status"] == "✅":
            return await interaction.followup.send(f"⚠️ Flag `{flag}` is already unclaimed on `{map_key.title()}`.", ephemeral=True)

        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE flags SET status='✅', role_id=NULL WHERE guild_id=$1 AND map=$2 AND flag=$3;", guild_id, map_key, flag)
            await conn.execute("UPDATE factions SET claimed_flag = NULL WHERE guild_id=$1 AND claimed_flag=$2 AND map=$3", guild_id, flag, map_key)

        try:
            await self.update_flag_message(guild, guild_id, map_key)
        except Exception as e:
            print(f"⚠️ Failed to update flag embed for {flag}: {e}")

        await log_action(guild, map_key, title="Flag Released", description=f"🏳️ Flag `{flag}` released by {interaction.user.mention}.", color=0x95A5A6)
        await log_faction_action(guild, action="Flag Released", faction_name=None, user=interaction.user, details=f"Flag `{flag}` released on `{map_key.title()}`.")

        embed = self.make_embed(title="✅ Flag Released", desc=(
            f"🏳️ **Flag:** `{flag}`\n"
            f"🗺️ **Map:** `{map_key.title()}`\n"
            f"👤 **Released by:** {interaction.user.mention}"
        ), color=0x95A5A6, author_icon="🏁", author_name="Flag Release")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Release(bot))
