import discord
from cogs import utils

class FlagManager:
    """Central handler for flag assign/release and embed sync."""

    @staticmethod
    def _canonical_flag_name(raw: str) -> str | None:
        """Case-insensitive lookup into utils.FLAGS and return the canonical name."""
        if not raw:
            return None
        r = raw.strip().lower()
        for f in utils.FLAGS:
            if f.lower() == r:
                return f
        return None

    @staticmethod
    def _ensure_role_in_guild(guild: discord.Guild, role: discord.Role) -> None:
        if role.guild.id != guild.id:
            raise ValueError("The selected role does not belong to this server.")

    @staticmethod
    async def assign_flag(
        guild: discord.Guild,
        map_key: str,
        flag: str,
        role: discord.Role,
        user: discord.Member
    ):
        """Assign a flag to a role/faction and update related systems."""
        guild_id = str(guild.id)
        await utils.ensure_connection()
        if utils.db_pool is None:
            raise RuntimeError("Database not initialized yet.")

        FlagManager._ensure_role_in_guild(guild, role)

        canonical_flag = FlagManager._canonical_flag_name(flag)
        if not canonical_flag:
            raise ValueError(f"Invalid flag name '{flag}'. Must be one of {', '.join(utils.FLAGS)}")

        flag_data = await utils.get_flag(guild_id, map_key, canonical_flag)
        if flag_data and flag_data["status"] == "❌":
            current_owner = flag_data["role_id"]
            raise ValueError(f"Flag '{canonical_flag}' is already owned by <@&{current_owner}>.")

        await utils.set_flag(guild_id, map_key, canonical_flag, "❌", str(role.id))

        async with utils.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE factions
                SET claimed_flag=$1
                WHERE guild_id=$2 AND role_id=$3 AND map=$4
                """,
                canonical_flag, guild_id, str(role.id), map_key
            )

        await FlagManager._refresh_embed_safe(guild, guild_id, map_key)

        await utils.log_action(
            guild,
            map_key,
            title="Flag Assigned",
            description=f"🏴 Flag `{canonical_flag}` assigned to {role.mention} by {user.mention}.",
            color=0x2ECC71
        )
        await utils.log_faction_action(
            guild,
            action="Flag Assigned",
            faction_name=role.name,
            user=user,
            details=f"Flag `{canonical_flag}` claimed on map `{map_key.title()}`.",
            map_key=map_key,
        )

    @staticmethod
    async def release_flag(
        guild: discord.Guild,
        map_key: str,
        flag: str,
        user: discord.Member
    ):
        """Release a flag back to unclaimed state."""
        guild_id = str(guild.id)
        await utils.ensure_connection()
        if utils.db_pool is None:
            raise RuntimeError("Database not initialized yet.")

        canonical_flag = FlagManager._canonical_flag_name(flag)
        if not canonical_flag:
            raise ValueError(f"Invalid flag name '{flag}'.")

        flag_data = await utils.get_flag(guild_id, map_key, canonical_flag)
        if not flag_data or flag_data["status"] == "✅":
            raise ValueError(f"Flag '{canonical_flag}' is already unclaimed on `{map_key.title()}`.")

        await utils.release_flag(guild_id, map_key, canonical_flag)

        async with utils.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE factions
                SET claimed_flag=NULL
                WHERE guild_id=$1 AND claimed_flag=$2 AND map=$3
                """,
                guild_id, canonical_flag, map_key
            )

        await FlagManager._refresh_embed_safe(guild, guild_id, map_key)

        await utils.log_action(
            guild,
            map_key,
            title="Flag Released",
            description=f"🏳️ Flag `{canonical_flag}` released by {user.mention}.",
            color=0x95A5A6
        )
        await utils.log_faction_action(
            guild,
            action="Flag Released",
            faction_name=None,
            user=user,
            details=f"Flag `{canonical_flag}` released on `{map_key.title()}`.",
            map_key=map_key,
        )

    @staticmethod
    async def _refresh_embed_safe(guild: discord.Guild, guild_id: str, map_key: str) -> None:
        """Refresh the map’s flag embed; fail silently if message/channel is missing."""
        if utils.db_pool is None:
            return
        try:
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
            except discord.NotFound:
                return

            embed = await utils.create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Could not refresh flag embed for {guild.name}/{map_key}: {e}")
