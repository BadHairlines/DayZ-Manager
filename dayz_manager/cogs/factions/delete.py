import discord
from discord import app_commands
from discord.ext import commands

from dayz_manager.cogs.utils.database import db_pool
from dayz_manager.cogs.utils.embeds import create_flag_embed
from dayz_manager.cogs.utils.logging import log_action, log_faction_action
from .utils import ensure_faction_table, make_embed

class FactionDelete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="delete-faction", description="Delete a faction and remove it from the database.")
    async def delete_faction(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admin only!", ephemeral=True)

        if db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)

        async with db_pool.acquire() as conn:
            faction = await conn.fetchrow("SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2", guild_id, name)

        if not faction:
            return await interaction.followup.send(f"❌ Faction `{name}` not found.", ephemeral=True)

        map_key = faction["map"].lower()
        claimed_flag = faction.get("claimed_flag") or None

        if claimed_flag:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute("UPDATE flags SET status='✅', role_id=NULL WHERE guild_id=$1 AND map=$2 AND flag=$3;", guild_id, map_key, claimed_flag)

                await log_action(guild, map_key, title="Flag Released (Faction Deleted)", description=f"🏳️ Flag **{claimed_flag}** was freed after `{name}` disbanded.")

                try:
                    embed = await create_flag_embed(guild_id, map_key)
                    async with db_pool.acquire() as conn:
                        row = await conn.fetchrow("SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2", guild_id, map_key)
                    if row:
                        ch = guild.get_channel(int(row["channel_id"]))
                        msg = await ch.fetch_message(int(row["message_id"])) if ch else None
                        if msg:
                            await msg.edit(embed=embed)
                except Exception as e:
                    print(f"⚠️ Failed to refresh flag display after faction deletion: {e}")
            except Exception as e:
                print(f"⚠️ Could not release flag {claimed_flag}: {e}")

        if (channel := guild.get_channel(int(faction["channel_id"]))):
            try:
                farewell_embed = make_embed("💀 Faction Disbanded", f"**{name}** has been officially disbanded. 🕊️")
                await channel.send(embed=farewell_embed)
                await channel.delete(reason="Faction disbanded")
            except Exception as e:
                print(f"⚠️ Failed to delete faction channel: {e}")

        if (role := guild.get_role(int(faction["role_id"]))):
            try:
                await role.delete(reason="Faction disbanded")
            except Exception as e:
                print(f"⚠️ Failed to delete faction role: {e}")

        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2", guild_id, name)

        await log_faction_action(guild, action="Faction Deleted", faction_name=name, user=interaction.user, details=f"Faction `{name}` was deleted by {interaction.user.mention}." )

        confirm_embed = make_embed("✅ Faction Deleted", f"Faction **{name}** has been completely removed and its flag freed.", color=0xE74C3C)
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(FactionDelete(bot))
