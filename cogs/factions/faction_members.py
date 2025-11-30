# cogs/faction_members.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table, make_embed


log = logging.getLogger("dayz-manager")


class FactionMembers(commands.Cog):
    """Handles adding/removing members from factions while syncing DB and Discord roles."""

    def __init__(self, bot):
        self.bot = bot
        self._locks = {}

    # =====================================
    # 🟩 ADD MEMBER
    # =====================================
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
            return await interaction.followup.send("🚫 Only admins can add members.", ephemeral=True)

        await utils.ensure_connection()
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)

        # --- Lock per guild to prevent race conditions ---
        lock = self._locks.setdefault(guild_id, discord.utils.MISSING)
        if lock is discord.utils.MISSING:
            import asyncio
            lock = asyncio.Lock()
            self._locks[guild_id] = lock

        async with lock:
            try:
                # --- Fetch faction record ---
                async with utils.safe_acquire() as conn:
                    faction_rec = await conn.fetchrow(
                        "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                        guild_id, faction_name
                    )

                if not faction_rec:
                    return await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)

                faction = dict(faction_rec)
                map_key = (faction.get("map") or "").lower()
                members = list(faction.get("member_ids") or [])

                # --- Skip if already in faction ---
                if str(member.id) in members:
                    role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason="Faction role resync (was already in DB)")
                        except discord.Forbidden:
                            log.warning(f"⚠️ Missing permission to reassign role {role.name} in {guild.name}.")
                    return await interaction.followup.send(f"⚠️ {member.mention} is already in `{faction_name}`.", ephemeral=True)

                # --- Add member to DB ---
                members.append(str(member.id))
                async with utils.safe_acquire() as conn:
                    await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

                # --- Assign faction role ---
                role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
                if not role:
                    msg = f"✅ Added to DB, but no valid faction role exists for `{faction_name}`. (Role may have been deleted.)"
                    log.warning(msg)
                    return await interaction.followup.send(msg, ephemeral=True)

                try:
                    await member.add_roles(role, reason=f"Added to faction '{faction_name}'")
                except discord.Forbidden:
                    log.warning(f"⚠️ Failed to assign role {role.name} to {member.display_name} in {guild.name}.")
                except Exception as e:
                    log.error(f"Error adding role to {member.display_name}: {e}", exc_info=True)

                # --- Log and notify ---
                await utils.log_faction_action(
                    guild,
                    action="Member Added",
                    faction_name=faction["faction_name"],
                    user=interaction.user,
                    details=f"{interaction.user.mention} added {member.mention} to faction `{faction['faction_name']}` (Map: `{map_key}`).",
                    map_key=map_key,
                )

                embed = make_embed("✅ Member Added", f"{member.mention} has joined **{faction_name}**! 🎉")
                await interaction.followup.send(embed=embed, ephemeral=True)
                log.info(f"✅ Added {member.display_name} to faction '{faction_name}' in {guild.name}.")

            except Exception as e:
                log.error(f"❌ Error adding faction member in {guild.name}: {e}", exc_info=True)
                await interaction.followup.send(f"❌ Failed to add member:\n```{e}```", ephemeral=True)

    # =====================================
    # 🟥 REMOVE MEMBER
    # =====================================
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
            return await interaction.followup.send("🚫 Only admins can remove members.", ephemeral=True)

        await utils.ensure_connection()
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)

        lock = self._locks.setdefault(guild_id, discord.utils.MISSING)
        if lock is discord.utils.MISSING:
            import asyncio
            lock = asyncio.Lock()
            self._locks[guild_id] = lock

        async with lock:
            try:
                async with utils.safe_acquire() as conn:
                    faction_rec = await conn.fetchrow(
                        "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                        guild_id, faction_name
                    )

                if not faction_rec:
                    return await interaction.followup.send(f"❌ Faction `{faction_name}` not found.", ephemeral=True)

                faction = dict(faction_rec)
                map_key = (faction.get("map") or "").lower()
                members = list(faction.get("member_ids") or [])

                # --- If not in faction, ensure role sync ---
                if str(member.id) not in members:
                    role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Faction sync (not in DB)")
                        except discord.Forbidden:
                            log.warning(f"⚠️ Missing permission to remove {role.name} from {member.display_name}.")
                    return await interaction.followup.send(f"⚠️ {member.mention} is not in `{faction_name}`.", ephemeral=True)

                # --- Remove from DB ---
                members.remove(str(member.id))
                async with utils.safe_acquire() as conn:
                    await conn.execute("UPDATE factions SET member_ids=$1 WHERE id=$2", members, faction["id"])

                # --- Remove Discord role ---
                role = guild.get_role(int(faction["role_id"])) if faction.get("role_id") else None
                if role:
                    try:
                        await member.remove_roles(role, reason=f"Removed from faction '{faction_name}'")
                    except discord.Forbidden:
                        log.warning(f"⚠️ Missing permission to remove {role.name} in {guild.name}.")
                    except Exception as e:
                        log.error(f"Error removing role from {member.display_name}: {e}", exc_info=True)

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
                log.info(f"🟥 Removed {member.display_name} from faction '{faction_name}' in {guild.name}.")

            except Exception as e:
                log.error(f"❌ Error removing faction member in {guild.name}: {e}", exc_info=True)
                await interaction.followup.send(f"❌ Failed to remove member:\n```{e}```", ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionMembers(bot))
