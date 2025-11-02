import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs import utils

class Reassign(commands.Cog, BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reassign", description="Reassign a flag from one faction/role to another.")
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(selected_map="Select which map this flag belongs to", flag="Enter the flag to reassign", new_role="Select the new faction/role to give the flag to")
    async def reassign(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str, new_role: discord.Role):
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
            return await interaction.followup.send(f"Flag `{flag}` is not currently owned — use `/assign` instead.", ephemeral=True)
        old_role_id = flag_data["role_id"]
        old_role = guild.get_role(int(old_role_id)) if old_role_id else None
        await utils.set_flag(guild_id, map_key, flag, "❌", str(new_role.id))
        async with utils.db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET claimed_flag=NULL WHERE guild_id=$1 AND role_id=$2 AND map=$3", guild_id, str(old_role_id), map_key)
            await conn.execute("UPDATE factions SET claimed_flag=$1 WHERE guild_id=$2 AND role_id=$3 AND map=$4", flag, guild_id, str(new_role.id), map_key)
        try:
            await self.update_flag_message(guild, guild_id, map_key)
        except Exception as e:
            print(f"Failed to update flag embed during reassignment: {e}")
        await utils.log_action(guild, map_key, title="Flag Reassigned", description=f"Flag `{flag}` reassigned from {old_role.mention if old_role else '`Unknown`'} → {new_role.mention} by {interaction.user.mention}.", color=0xF1C40F)
        await utils.log_faction_action(guild, action="Flag Reassigned", faction_name=new_role.name, user=interaction.user, details=f"Transferred ownership of `{flag}` from {old_role.mention if old_role else 'Unknown'}.")
        embed = self.make_embed(
            title="Flag Reassigned",
            desc=(f"Flag: `{flag}`\nMap: `{map_key.title()}`\nOld Owner: {old_role.mention if old_role else '`None`'}\nNew Owner: {new_role.mention}\nBy: {interaction.user.mention}"),
            color=0xF1C40F,
            author_icon="🔁",
            author_name="Flag Transfer"
        )
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Reassign(bot))
