import asyncio
import logging
import discord
from cogs import utils

log = logging.getLogger("dayz-manager")


class FlagManager:
    """Clean flag system: no factions, no role ownership — just flag state."""

    _locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _canonical_flag_name(raw: str) -> str | None:
        if not raw:
            return None
        r = raw.strip().lower()
        for f in utils.FLAGS:
            if f.lower() == r:
                return f
        return None

    @staticmethod
    def _get_lock(guild_id: str, map_key: str) -> asyncio.Lock:
        key = f"{guild_id}:{map_key}"
        if key not in FlagManager._locks:
            FlagManager._locks[key] = asyncio.Lock()
        return FlagManager._locks[key]

    # ---------------- ASSIGN ----------------
    @staticmethod
    async def assign_flag(
        guild: discord.Guild,
        map_key: str,
        flag: str,
        user: discord.Member
    ):
        guild_id = str(guild.id)
        await utils.ensure_connection()

        canonical_flag = FlagManager._canonical_flag_name(flag)
        if not canonical_flag:
            raise ValueError(f"Invalid flag name '{flag}'.")

        lock = FlagManager._get_lock(guild_id, map_key)

        async with lock:
            flag_data = await utils.get_flag(guild_id, map_key, canonical_flag)

            if flag_data and flag_data["status"] == "❌":
                raise ValueError(f"Flag '{canonical_flag}' is already claimed.")

            await utils.set_flag(
                guild_id,
                map_key,
                canonical_flag,
                "❌",
                str(user.id)  # optional: store who claimed it (NOT a faction system)
            )

            await FlagManager._refresh_embed_safe(guild, guild_id, map_key)

            log.info(f"✅ Flag '{canonical_flag}' assigned in {guild.name} ({map_key}).")

    # ---------------- RELEASE ----------------
    @staticmethod
    async def release_flag(
        guild: discord.Guild,
        map_key: str,
        flag: str,
        user: discord.Member
    ):
        guild_id = str(guild.id)
        await utils.ensure_connection()

        canonical_flag = FlagManager._canonical_flag_name(flag)
        if not canonical_flag:
            raise ValueError(f"Invalid flag name '{flag}'.")

        lock = FlagManager._get_lock(guild_id, map_key)

        async with lock:
            flag_data = await utils.get_flag(guild_id, map_key, canonical_flag)

            if not flag_data or flag_data["status"] == "✅":
                raise ValueError(f"Flag '{canonical_flag}' is already unclaimed.")

            await utils.release_flag(guild_id, map_key, canonical_flag)

            await FlagManager._refresh_embed_safe(guild, guild_id, map_key)

            log.info(f"🏳️ Flag '{canonical_flag}' released in {guild.name} ({map_key}).")

    # ---------------- EMBED REFRESH ----------------
    @staticmethod
    async def _refresh_embed_safe(
        guild: discord.Guild,
        guild_id: str,
        map_key: str
    ):
        try:
            await utils.ensure_connection()

            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
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
            pass
        except Exception as e:
            log.error(f"Failed to refresh embed: {e}", exc_info=True)
