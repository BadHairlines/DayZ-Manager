import discord
from cogs import utils

class FlagManager:
    """Central handler for all flag operations (assign, release, sync)."""

    @staticmethod
    async def assign_flag(guild: discord.Guild, map_key: str, flag: str, role: discord.Role, user: discord.Member):
        """Assign a flag to a role/faction and update all related systems."""
        guild_id = str(guild.id)
        await utils.ensure_connection()

        # ✅ Validate flag
        if flag not in utils.FLAGS:
            raise ValueError(f"Invalid flag name '{flag}'. Must be one of {', '.join(utils.FLAGS)}")

        # ✅ Check if flag already claimed
        flag_data = await utils.get_flag(guild_id, map_key, flag)
        if flag_data and flag_data["status"] == "❌":
            current_owner = flag_data["role_id"]
            raise ValueError(f"Flag '{flag}' is already owned by <@&{current_owner}>.")

        # ✅ Assign flag
        await utils.set_flag(guild_id, map_key, flag, "❌", str(role.id))

        # ✅ Sync with faction record (if exists)
        faction = await utils.get_faction_by_flag(guild_id, flag)
        if not faction:
            async with utils.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE factions
                    SET claimed_flag=$1
                    WHERE guild_id=$2 AND role_id=$3 AND map=$4
                    """,
                    flag, guild_id, str(role.id), map_key
                )

        # ✅ Refresh embed
        try:
            await FlagManager._refresh_embed(guild, guild_id, map_key)
        except Exception as e:
            print(f"⚠️ Failed to refresh flag embed for {flag}: {e}")

        # ✅ Log
        await utils.log_action(
            guild,
            map_key,
            title="Flag Assigned",
            description=f"🏴 Flag `{flag}` assigned to {role.mention} by {user.mention}.",
            color=0x2ECC71
        )
        await utils.log_faction_action(
            guild,
            action="Flag Assigned",
            faction_name=role.name,
            user=user,
            details=f"Flag `{flag}` claimed on map `{map_key.title()}`.",
            map_key=map_key,  # 👈 required
        )

    # -----------------------------------------------------------------

    @staticmethod
    async def release_flag(guild: discord.Guild, map_key: str, flag: str, user: discord.Member):
        """Release a flag back to unclaimed state."""
        guild_id = str(guild.id)
        await utils.ensure_connection()

        # ✅ Validate flag
        if flag not in utils.FLAGS:
            raise ValueError(f"Invalid flag name '{flag}'.")

        # ✅ Check current ownership
        flag_data = await utils.get_flag(guild_id, map_key, flag)
        if not flag_data or flag_data["status"] == "✅":
            raise ValueError(f"Flag '{flag}' is already unclaimed on `{map_key.title()}`.")

        # ✅ Release in DB
        await utils.release_flag(guild_id, map_key, flag)

        # ✅ Unlink from factions table
        async with utils.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE factions
                SET claimed_flag=NULL
                WHERE guild_id=$1 AND claimed_flag=$2 AND map=$3
                """,
                guild_id, flag, map_key
            )

        # ✅ Refresh embed
        try:
            await FlagManager._refresh_embed(guild, guild_id, map_key)
        except Exception as e:
            print(f"⚠️ Failed to refresh flag embed for {flag}: {e}")

        # ✅ Log
        await utils.log_action(
            guild,
            map_key,
            title="Flag Released",
            description=f"🏳️ Flag `{flag}` released by {user.mention}.",
            color=0x95A5A6
        )
        await utils.log_faction_action(
            guild,
            action="Flag Released",
            faction_name=None,
            user=user,
            details=f"Flag `{flag}` released on `{map_key.title()}`.",
            map_key=map_key,  # 👈 required
        )

    # -----------------------------------------------------------------

    @staticmethod
    async def _refresh_embed(guild: discord.Guild, guild_id: str, map_key: str):
        """Internal utility to refresh the flag embed display."""
        async with utils.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )
        if not row:
            return
        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            return
        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await utils.create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Could not edit flag message: {e}")
