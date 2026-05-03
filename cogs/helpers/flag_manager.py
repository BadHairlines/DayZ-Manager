import asyncio
import logging
import discord

from cogs import utils

log = logging.getLogger("dayz-manager")


class FlagManager:
    """
    Service layer for flag operations.
    No UI logic. No commands. Pure business rules.
    """

    _locks: dict[str, asyncio.Lock] = {}

    # -----------------------------
    # HELPERS
    # -----------------------------
    @staticmethod
    def _normalize_flag(raw: str) -> str | None:
        if not raw:
            return None

        raw = raw.strip().lower()

        for flag in utils.FLAGS:
            if flag.lower() == raw:
                return flag

        return None

    @staticmethod
    def _lock_key(guild_id: str, map_key: str) -> str:
        return f"{guild_id}:{map_key}"

    @classmethod
    def _get_lock(cls, guild_id: str, map_key: str) -> asyncio.Lock:
        key = cls._lock_key(guild_id, map_key)

        if key not in cls._locks:
            cls._locks[key] = asyncio.Lock()

        return cls._locks[key]

    # -----------------------------
    # ASSIGN FLAG
    # -----------------------------
    @classmethod
    async def assign_flag(
        cls,
        guild: discord.Guild,
        map_key: str,
        flag: str,
        user: discord.Member
    ):
        guild_id = str(guild.id)

        canonical = cls._normalize_flag(flag)
        if not canonical:
            raise ValueError("Invalid flag.")

        lock = cls._get_lock(guild_id, map_key)

        async with lock:
            current = await utils.get_flag(guild_id, map_key, canonical)

            if current and current["status"] == "❌":
                raise ValueError("Flag already claimed.")

            await utils.set_flag(
                guild_id,
                map_key,
                canonical,
                "❌",
                str(user.id)
            )

            await cls._refresh_embed(guild, guild_id, map_key)

            log.info(f"Flag assigned: {canonical} in {guild.name} ({map_key})")

    # -----------------------------
    # RELEASE FLAG
    # -----------------------------
    @classmethod
    async def release_flag(
        cls,
        guild: discord.Guild,
        map_key: str,
        flag: str,
        user: discord.Member
    ):
        guild_id = str(guild.id)

        canonical = cls._normalize_flag(flag)
        if not canonical:
            raise ValueError("Invalid flag.")

        lock = cls._get_lock(guild_id, map_key)

        async with lock:
            current = await utils.get_flag(guild_id, map_key, canonical)

            if not current or current["status"] == "✅":
                raise ValueError("Flag already unclaimed.")

            await utils.release_flag(guild_id, map_key, canonical)

            await cls._refresh_embed(guild, guild_id, map_key)

            log.info(f"Flag released: {canonical} in {guild.name} ({map_key})")

    # -----------------------------
    # EMBED REFRESH
    # -----------------------------
    @classmethod
    async def _refresh_embed(
        cls,
        guild: discord.Guild,
        guild_id: str,
        map_key: str
    ):
        try:
            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT channel_id, message_id
                    FROM flag_messages
                    WHERE guild_id=$1 AND map=$2
                    """,
                    guild_id,
                    map_key
                )

            if not row:
                return

            channel = guild.get_channel(int(row["channel_id"]))
            if not channel:
                return

            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await utils.create_flag_embed(guild_id, map_key)

            await msg.edit(embed=embed)

        except discord.NotFound:
            return

        except Exception as e:
            log.error(f"Embed refresh failed: {e}", exc_info=True)
