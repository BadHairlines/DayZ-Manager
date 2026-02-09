import asyncio
import logging

import asyncpg
import discord
from cogs import utils

log = logging.getLogger("dayz-manager")


class FlagManager:
    """Central handler for flag assignment, release, and embed refresh."""

    _locks: dict[str, asyncio.Lock] = {}

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
        """Validate that a role belongs to the current guild."""
        if role.guild.id != guild.id:
            raise ValueError("The selected role does not belong to this server.")

    @staticmethod
    def _get_lock(guild_id: str, map_key: str) -> asyncio.Lock:
        """Get or create a map-specific async lock."""
        key = f"{guild_id}:{map_key}"
        if key not in FlagManager._locks:
            FlagManager._locks[key] = asyncio.Lock()
        return FlagManager._locks[key]

    @staticmethod
    async def assign_flag(guild: discord.Guild, map_key: str, flag: str, role: discord.Role, user: discord.Member):
        """Assign a flag to a role/faction and update related systems."""
        guild_id = str(guild.id)
        await utils.ensure_connection()

        FlagManager._ensure_role_in_guild(guild, role)
        canonical_flag = FlagManager._canonical_flag_name(flag)
        if not canonical_flag:
            raise ValueError(f"Invalid flag name '{flag}'. Must be one of: {', '.join(utils.FLAGS)}")

        lock = FlagManager._get_lock(guild_id, map_key)
        async with lock:
            try:
                async with utils.safe_acquire() as conn:
                    existing_flag = await conn.fetchval(
                        """
                        SELECT claimed_flag
                        FROM factions
                        WHERE guild_id=$1 AND role_id=$2 AND map=$3
                        """,
                        guild_id, str(role.id), map_key
                    )
                if existing_flag and existing_flag != canonical_flag:
                    raise ValueError(
                        f"{role.mention} already owns `{existing_flag}` on `{map_key.title()}`."
                    )
                if existing_flag == canonical_flag:
                    raise ValueError(
                        f"{role.mention} already owns `{canonical_flag}` on `{map_key.title()}`."
                    )
            except asyncpg.UndefinedTableError:
                log.debug("Factions table not found; skipping claimed_flag check.")
            except ValueError:
                raise
            except Exception as exc:
                log.warning(f"Could not verify existing claimed flag for {guild.name}: {exc}")

            flag_data = await utils.get_flag(guild_id, map_key, canonical_flag)
            if flag_data and flag_data["status"] == "❌":
                current_owner = flag_data["role_id"]
                raise ValueError(f"Flag '{canonical_flag}' is already owned by <@&{current_owner}>.")

            await utils.set_flag(guild_id, map_key, canonical_flag, "❌", str(role.id))

            async with utils.safe_acquire() as conn:
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
                guild, map_key,
                title="Flag Assigned",
                description=f"🏴 `{canonical_flag}` assigned to {role.mention} by {user.mention}.",
                color=0x2ECC71
            )
            await utils.log_faction_action(
                guild,
                action="Flag Assigned",
                faction_name=role.name,
                user=user,
                details=f"Flag `{canonical_flag}` claimed on `{map_key.title()}`.",
                map_key=map_key,
            )

            log.info(f"✅ Flag '{canonical_flag}' assigned to {role.name} in {guild.name} ({map_key}).")

    @staticmethod
    async def release_flag(guild: discord.Guild, map_key: str, flag: str, user: discord.Member):
        """Release a flag back to unclaimed state."""
        guild_id = str(guild.id)
        await utils.ensure_connection()

        canonical_flag = FlagManager._canonical_flag_name(flag)
        if not canonical_flag:
            raise ValueError(f"Invalid flag name '{flag}'.")

        lock = FlagManager._get_lock(guild_id, map_key)
        async with lock:
            flag_data = await utils.get_flag(guild_id, map_key, canonical_flag)
            if not flag_data or flag_data["status"] == "✅":
                raise ValueError(f"Flag '{canonical_flag}' is already unclaimed on `{map_key.title()}`.")

            await utils.release_flag(guild_id, map_key, canonical_flag)

            async with utils.safe_acquire() as conn:
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
                guild, map_key,
                title="Flag Released",
                description=f"🏳️ `{canonical_flag}` released by {user.mention}.",
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

            log.info(f"✅ Flag '{canonical_flag}' released by {user.display_name} in {guild.name} ({map_key}).")

    @staticmethod
    async def _refresh_embed_safe(guild: discord.Guild, guild_id: str, map_key: str) -> None:
        """Refresh the map’s flag embed; fail silently if message/channel is missing."""
        try:
            await utils.ensure_connection()
        except Exception as e:
            log.warning(f"⚠️ Database unavailable — skipping flag embed refresh: {e}")
            return

        try:
            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id, map_key
                )
            if not row:
                log.debug(f"No flag message found for {guild.name}/{map_key}.")
                return

            channel = guild.get_channel(int(row["channel_id"]))
            if not channel:
                log.warning(f"⚠️ Channel missing for {guild.name}/{map_key}.")
                return

            try:
                msg = await channel.fetch_message(int(row["message_id"]))
            except discord.NotFound:
                log.warning(f"⚠️ Flag message deleted for {guild.name}/{map_key}.")
                return

            embed = await utils.create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
            log.info(f"🔄 Refreshed flag embed for {guild.name}/{map_key}.")
        except Exception as e:
            log.error(f"❌ Could not refresh flag embed for {guild.name}/{map_key}: {e}", exc_info=True)
