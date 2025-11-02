import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils
from .faction_utils import make_embed, ensure_faction_table

class FactionSync(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="sync-factions", description="Synchronize factions and flags both ways.")
    async def sync_factions(self, interaction:discord.Interaction, confirm:bool):
        await interaction.response.defer(thinking=True, ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("Only administrators can run this command.", ephemeral=True)
        if not confirm:
            return await interaction.followup.send("Sync cancelled — confirmation not given.", ephemeral=True)
        guild = interaction.guild
        if utils.db_pool is None: return await interaction.followup.send("Database not initialized.", ephemeral=True)
        await ensure_faction_table()
        updated_flags = updated_factions = skipped = total_flags = total_factions = 0
        async with utils.db_pool.acquire() as conn:
            factions = await conn.fetch("SELECT * FROM factions WHERE guild_id=$1", str(guild.id))
            flags = await conn.fetch("SELECT map,flag,role_id FROM flags WHERE guild_id=$1", str(guild.id))
            total_factions, total_flags = len(factions), len(flags)
            role_to_flag = {r["role_id"]:(r["map"],r["flag"]) for r in flags if r["role_id"]}
            for f in factions:
                r=f["role_id"]
                if not guild.get_role(int(r)) or r not in role_to_flag:
                    skipped+=1; continue
                m,fl=role_to_flag[r]
                await utils.log_faction_action(guild, action="Faction Ownership Verified", faction_name=f["faction_name"], user=interaction.user, details=f"{f['faction_name']} confirmed owning {fl} on {m}.")
                updated_factions+=1
            for fl in flags:
                m,flag_name,r=fl["map"],fl["flag"],fl["role_id"]
                if not r: continue
                if any(f["role_id"]==r for f in factions): continue
                role=guild.get_role(int(r))
                if not role: continue
                await utils.log_faction_action(guild, action="Flag Ownership Unlinked", faction_name=None, user=interaction.user, details=f"Flag {flag_name} on {m} owned by {role.name} but no faction exists.")
                updated_flags+=1
            for f in factions:
                if not guild.get_role(int(f["role_id"])):
                    await utils.log_faction_action(guild, action="Faction Role Missing", faction_name=f["faction_name"], user=interaction.user, details=f"Role <@&{f['role_id']}> missing for {f['faction_name']}.")
                    skipped+=1
        embed=make_embed("Two-Way Faction Sync Complete",f"Guild: {guild.name}\nFlags Checked: {total_flags}\nFactions Checked: {total_factions}\nFactions Updated: {updated_factions}\nFlags Reviewed: {updated_flags}\nSkipped: {skipped}\nSync completed successfully.",color=0x3498DB)
        embed.set_footer(text="Faction ↔ Flag Sync • DayZ Manager",icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot): await bot.add_cog(FactionSync(bot))
