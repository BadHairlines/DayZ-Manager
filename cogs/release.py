import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs import utils

class Release(commands.Cog, BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="release", description="Release a claimed flag and make it available again.")
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(selected_map="Select the map containing the flag to release", flag="Enter the flag name to release")
    async def release(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str):
        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = normalize_map(selected_map)
        if utils.db_pool is None:
            return await interaction.followup.send("Database not initialized. Please restart the bot.", ephemeral=True)
        if flag not in utils.FLAGS:
            return await interaction.followup.send(f"Invalid flag name. Must be one of:\n`{', '.join(utils.FLAGS)}`", ephemeral=True)
        flag_data = await utils.get_flag(guild_id, map_key, flag)
        if not flag_data or flag_data["status"] == "✅":
            return await interaction.followup.send(f"Flag `{flag}` is already unclaimed on `{map_key.title()}`.", ephemeral=True)
        await utils.release_flag(guild_id, map_key, flag)
        async with utils.db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET claimed_flag=NULL WHERE guild_id=$1 AND claimed_flag=$2 AND map=$3", guild_id, flag, map_key)
        try:
            await self.update_flag_message(guild, guild_id, map_key)
        except Exception as e:
            print(f"Failed to update flag embed for {flag}: {e}")
        await utils.log_action(guild, map_key, title="Flag Released", description=f"Flag `{flag}` released by {interaction.user.mention}.", color=0x95A5A6)
        await utils.log_faction_action(guild, action="Flag Released", faction_name=None, user=interaction.user, details=f"Flag `{flag}` released on `{map_key.title()}`.")
        embed = self.make_embed(
            title="Flag Released",
            desc=(f"Flag: `{flag}`\nMap: `{map_key.title()}`\nReleased by: {interaction.user.mention}"),
            color=0x95A5A6,
            author_icon="🏁",
            author_name="Flag Release"
        )
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Release(bot))
