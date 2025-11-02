import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import db_pool
from .faction_utils import ensure_faction_table, make_embed

class FactionDelete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="delete-faction", description="Delete a faction and remove it from the database.")
    async def delete_faction(self, interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admin only!", ephemeral=True)

        await ensure_faction_table()
        guild = interaction.guild
        async with db_pool.acquire() as conn:
            faction = await conn.fetchrow("SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2", str(guild.id), name)
        if not faction:
            return await interaction.followup.send(f"❌ Faction `{name}` not found.", ephemeral=True)

        if (ch := guild.get_channel(int(faction["channel_id"]))):
            await ch.send(embed=make_embed("💀 Faction Disbanded", f"**{name}** has been disbanded."))
            await ch.delete()

        if (r := guild.get_role(int(faction["role_id"]))):
            await r.delete()

        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2", str(guild.id), name)

        await interaction.followup.send(embed=make_embed("✅ Deleted", f"Faction **{name}** deleted successfully.", 0xE74C3C), ephemeral=True)

async def setup(bot):
    await bot.add_cog(FactionDelete(bot))
