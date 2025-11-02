import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils
from .faction_utils import ensure_faction_table, make_embed

class FactionDelete(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="delete-faction", description="Delete a faction and remove it from the database.")
    async def delete_faction(self, interaction:discord.Interaction, name:str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("Admin only.", ephemeral=True)
        if utils.db_pool is None: raise RuntimeError("Database not initialized.")
        await ensure_faction_table()
        guild, guild_id = interaction.guild, str(interaction.guild.id)
        async with utils.db_pool.acquire() as conn:
            faction = await conn.fetchrow("SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2", guild_id, name)
        if not faction: return await interaction.followup.send(f"Faction {name} not found.", ephemeral=True)
        claimed_flag = faction.get("claimed_flag") or None
        if claimed_flag:
            try:
                await utils.set_flag(guild_id, faction["map"], claimed_flag, "✅", None)
                await utils.log_action(guild, faction["map"], title="Flag Released (Faction Deleted)", description=f"Flag {claimed_flag} freed after {name} disbanded.")
                try:
                    embed = await utils.create_flag_embed(guild_id, faction["map"])
                    async with utils.db_pool.acquire() as conn:
                        row = await conn.fetchrow("SELECT channel_id,message_id FROM flag_messages WHERE guild_id=$1 AND map=$2", guild_id, faction["map"])
                    if row:
                        ch=guild.get_channel(int(row["channel_id"]))
                        msg=await ch.fetch_message(int(row["message_id"]))
                        await msg.edit(embed=embed)
                except Exception: pass
            except Exception: pass
        if (channel := guild.get_channel(int(faction["channel_id"]))):
            try:
                farewell = make_embed("Faction Disbanded", f"{name} has been officially disbanded.")
                await channel.send(embed=farewell); await channel.delete(reason="Faction disbanded")
            except Exception: pass
        if (role := guild.get_role(int(faction["role_id"]))):
            try: await role.delete(reason="Faction disbanded")
            except Exception: pass
        async with utils.db_pool.acquire() as conn:
            await conn.execute("DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2", guild_id, name)
        await utils.log_faction_action(guild, action="Faction Deleted", faction_name=name, user=interaction.user, details=f"Faction {name} deleted by {interaction.user.mention}.")
        confirm = make_embed("Faction Deleted", f"Faction {name} has been removed and its flag freed.", color=0xE74C3C)
        await interaction.followup.send(embed=confirm, ephemeral=True)

async def setup(bot): await bot.add_cog(FactionDelete(bot))
