import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils
from .faction_utils import ensure_faction_table, make_embed


class FactionMembers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="add-member",
        description="Add a member to a faction."
    )
    @app_commands.describe(
        faction_name="Exact faction name (case-insensitive)",
        member="Member to add"
    )
    async def add_member(self, interaction: discord.Interaction, faction_name: str, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Only admins can add members.", ephemeral=True)

        if utils.db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild
        async with utils.db_pool.acquire() as conn:
            faction_rec = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), faction_name
            )

        if not faction_rec:
            return await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)

        faction = dict(faction_rec)
        map_key = (faction.get("map") or "").lower()
        members = list(faction.get("member_ids") or [])

        if str(member.id) in members:
            role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Faction sync (was already in DB)")
                except Exception as e:
                    print(f"⚠️ Failed to add role to {member}: {e}")
            return await interaction.followup.send(f"⚠️ {member.mention} is already in `{faction_name}`.", ephemeral=True)

        members.append(str(member.id))
        async with utils.db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

        role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
        if not role:
            await interaction.followup.send(
                f"✅ Added to DB, but no valid faction role was found to assign. (Check role_id for `{faction_name}`.)",
                ephemeral=True
            )
        else:
            try:
                await member.add_roles(role, reason="Added to faction")
            except Exception as e:
                print(f"⚠️ Failed to add role to {member}: {e}")

        await utils.log_faction_action(
            guild,
            action="Member Added",
            faction_name=faction["faction_name"],
            user=interaction.user,
            details=f"{interaction.user.mention} added {member.mention} to faction `{faction['faction_name']}` (Map: `{map_key}`).",
            map_key=map_key,
        )

        embed = make_embed("✅ Member Added", f"{member.mention} joined **{faction_name}**! 🎉")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="remove-member",
        description="Remove a member from a faction."
    )
    @app_commands.describe(
        faction_name="Exact faction name (case-insensitive)",
        member="Member to remove"
    )
    async def remove_member(self, interaction: discord.Interaction, faction_name: str, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Only admins can remove members.", ephemeral=True)

        if utils.db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild
        async with utils.db_pool.acquire() as conn:
            faction_rec = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), faction_name
            )

        if not faction_rec:
            return await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)

        faction = dict(faction_rec)
        map_key = (faction.get("map") or "").lower()
        members = list(faction.get("member_ids") or [])

        if str(member.id) not in members:
            role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Faction sync (not in DB)")
                except Exception as e:
                    print(f"⚠️ Failed to remove role from {member}: {e}")
            return await interaction.followup.send(f"⚠️ {member.mention} is not in `{faction_name}`.", ephemeral=True)

        members.remove(str(member.id))
        async with utils.db_pool.acquire() as conn:
            await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

        role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
        if role:
            try:
                await member.remove_roles(role, reason="Removed from faction")
            except Exception as e:
                print(f"⚠️ Failed to remove role from {member}: {e}")

        await utils.log_faction_action(
            guild,
            action="Member Removed",
            faction_name=faction["faction_name"],
            user=interaction.user,
            details=f"{interaction.user.mention} removed {member.mention} from faction `{faction['faction_name']}` (Map: `{map_key}`).",
            map_key=map_key,
        )

        embed = make_embed("👋 Member Removed", f"{member.mention} has been removed from **{faction_name}**.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionMembers(bot))
