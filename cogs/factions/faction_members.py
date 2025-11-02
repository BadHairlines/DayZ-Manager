import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils  # ✅ Use full utils module for safe access
from .faction_utils import ensure_faction_table, make_embed


class FactionMembers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================
    # ➕ /add-member
    # ============================================
    @app_commands.command(name="add-member", description="Add a member to a faction.")
    async def add_member(self, interaction: discord.Interaction, faction_name: str, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Only admins can add members.", ephemeral=True)

        # 🧩 Ensure DB is initialized and table exists
        if utils.db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild

        async with utils.db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), faction_name
            )

        if not faction:
            return await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)

        members = faction["member_ids"] or []
        if str(member.id) in members:
            return await interaction.followup.send(f"⚠️ {member.mention} is already in `{faction_name}`.", ephemeral=True)

        members.append(str(member.id))
        async with utils.db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

        if (role := guild.get_role(int(faction["role_id"]))):
            await member.add_roles(role)

        embed = make_embed("✅ Member Added", f"{member.mention} joined **{faction_name}**! 🎉")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ============================================
    # ➖ /remove-member
    # ============================================
    @app_commands.command(name="remove-member", description="Remove a member from a faction.")
    async def remove_member(self, interaction: discord.Interaction, faction_name: str, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Only admins can remove members.", ephemeral=True)

        # 🧩 Ensure DB is initialized and table exists
        if utils.db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild

        async with utils.db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), faction_name
            )

        if not faction:
            return await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)

        members = faction["member_ids"] or []
        if str(member.id) not in members:
            return await interaction.followup.send(f"⚠️ {member.mention} is not in `{faction_name}`.", ephemeral=True)

        members.remove(str(member.id))
        async with utils.db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

        if (role := guild.get_role(int(faction["role_id"]))):
            await member.remove_roles(role)

        embed = make_embed("👋 Member Removed", f"{member.mention} has been removed from **{faction_name}**.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionMembers(bot))
