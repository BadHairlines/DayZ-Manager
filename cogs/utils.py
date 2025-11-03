# cogs/utils.py
# Core utilities shared by the DayZ Manager cogs.
# Provides: db_pool, ensure_connection(), init_db(), FLAGS, MAP_DATA,
# get_flag(), get_all_flags(), set_flag(), release_flag(), create_flag_embed(),
# log_action(), log_faction_action().

from __future__ import annotations

import os
import asyncio
from typing import Optional, List, Dict, Any, Tuple

import asyncpg
import discord

# ==============================
# 🔌 Database pool & bootstrap
# ==============================

db_pool: Optional[asyncpg.Pool] = None

DEFAULT_DB_ENV_KEYS = ("DATABASE_URL", "POSTGRES_URL", "PG_URL")


async def ensure_connection() -> asyncpg.Pool:
    """
    Ensure a global asyncpg pool exists and core tables are created.
    Safe to call multiple times.
    """
    global db_pool
    if db_pool is not None:
        return db_pool

    dsn = None
    for key in DEFAULT_DB_ENV_KEYS:
        if os.getenv(key):
            dsn = os.getenv(key)
            break
    if not dsn:
        raise RuntimeError(
            "No database URL found. Set one of: DATABASE_URL, POSTGRES_URL, PG_URL"
        )

    # Create pool
    db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

    # Create core tables
    async with db_pool.acquire() as conn:
        # Flags table: one row per guild+map+flag
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flags (
                guild_id TEXT NOT NULL,
                map      TEXT NOT NULL,
                flag     TEXT NOT NULL,
                status   TEXT NOT NULL,   -- '✅' or '❌'
                role_id  TEXT,            -- owning role when claimed
                PRIMARY KEY (guild_id, map, flag)
            );
        """)

        # Where the flag embed lives (Setup cog also ensures this)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flag_messages (
                guild_id   TEXT NOT NULL,
                map        TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                log_channel_id TEXT,
                PRIMARY KEY (guild_id, map)
            );
        """)

        # Generic action logs table (optional)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS action_logs (
                id BIGSERIAL PRIMARY KEY,
                guild_id TEXT NOT NULL,
                map      TEXT,
                title    TEXT NOT NULL,
                description TEXT NOT NULL,
                color    INT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Faction logs table (used by log_faction_action)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS faction_logs (
                id BIGSERIAL PRIMARY KEY,
                guild_id TEXT NOT NULL,
                action TEXT NOT NULL,
                faction_name TEXT,
                user_id TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

    return db_pool


# Some code still calls init_db(); keep it as an alias.
async def init_db() -> asyncpg.Pool:
    return await ensure_connection()


# ==============================
# 🗺️ Static game data
# ==============================

# The set of supported flags. Add/remove as you wish.
FLAGS: List[str] = [
    "Wolf", "APA", "NAPA", "Coyote", "Bear", "Raven", "Boar", "Eagle", "Stag", "Viper"
]

# Map metadata used in embeds / setup flows
MAP_DATA: Dict[str, Dict[str, Any]] = {
    "livonia": {
        "name": "Livonia",
        "image": "https://i.postimg.cc/0jv3QWZ3/livonia.png",
    },
    "chernarus": {
        "name": "Chernarus",
        "image": "https://i.postimg.cc/Px6qkJVz/chernarus.png",
    },
    "sakhal": {
        "name": "Sakhal",
        "image": "https://i.postimg.cc/0y9wDd0v/sakhal.png",
    },
}


# ==============================
# 🧱 Flag storage helpers
# ==============================

async def get_flag(guild_id: str, map_key: str, flag_name: str) -> Optional[asyncpg.Record]:
    await ensure_connection()
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM flags WHERE guild_id=$1 AND map=$2 AND flag=$3",
            guild_id, map_key, flag_name
        )


async def get_all_flags(guild_id: str, map_key: str) -> List[asyncpg.Record]:
    await ensure_connection()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM flags WHERE guild_id=$1 AND map=$2 ORDER BY flag ASC",
            guild_id, map_key
        )
    return list(rows)


async def set_flag(guild_id: str, map_key: str, flag_name: str, status: str, role_id: Optional[str]) -> None:
    """
    Upsert a flag row. status is '✅' for unclaimed, '❌' for claimed.
    """
    await ensure_connection()
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET status=EXCLUDED.status, role_id=EXCLUDED.role_id
            """,
            guild_id, map_key, flag_name, status, role_id
        )


async def release_flag(guild_id: str, map_key: str, flag_name: str) -> None:
    """Mark a flag as unclaimed."""
    await set_flag(guild_id, map_key, flag_name, "✅", None)


# ==============================
# 🧾 Embeds & logging
# ==============================

def _split_claims(rows: List[asyncpg.Record]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Returns (unclaimed_names, claimed_pairs[(flag, role_id)])
    """
    unclaimed: List[str] = []
    claimed: List[Tuple[str, str]] = []
    for r in rows:
        if r["status"] == "✅":
            unclaimed.append(r["flag"])
        else:
            claimed.append((r["flag"], r["role_id"]))
    return unclaimed, claimed


async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    """
    Build a summary embed for all flags on a map.
    """
    await ensure_connection()

    rows = await get_all_flags(guild_id, map_key)
    # If flags table empty for this map, preseed with all unclaimed
    if not rows:
        for f in FLAGS:
            await set_flag(guild_id, map_key, f, "✅", None)
        rows = await get_all_flags(guild_id, map_key)

    map_info = MAP_DATA.get(map_key, {"name": map_key.title(), "image": None})
    unclaimed, claimed = _split_claims(rows)

    embed = discord.Embed(
        title=f"🏴 Flags — {map_info['name']}",
        description="Assign or release flags using the buttons below.",
        color=0x2B90D9,
    )
    embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    embed.timestamp = discord.utils.utcnow()

    # Thumbnail/hero image if provided
    if map_info.get("image"):
        embed.set_image(url=map_info["image"])

    if claimed:
        lines = [f"❌ **{flag}** — <@&{rid}>" for flag, rid in claimed]
        embed.add_field(name="Claimed", value="\n".join(lines)[:1024] or "—", inline=False)
    else:
        embed.add_field(name="Claimed", value="*(none)*", inline=False)

    if unclaimed:
        # group in comma list
        embed.add_field(name="Available", value=", ".join(unclaimed)[:1024] or "—", inline=False)
    else:
        embed.add_field(name="Available", value="*(none)*", inline=False)

    return embed


async def _resolve_logs_channel(
    guild: discord.Guild,
    map_key: Optional[str] = None,
    prefer_category: bool = True,
) -> Optional[discord.TextChannel]:
    """
    Find or create a sensible logs channel for the given map.
    - If prefer_category, create/find category "📜 DayZ Manager Logs" and channel per map.
    - fallback to guild.system_channel
    """
    channel: Optional[discord.TextChannel] = None
    try:
        category = None
        if prefer_category:
            category = discord.utils.get(guild.categories, name="📜 DayZ Manager Logs")
            if category is None:
                try:
                    category = await guild.create_category(
                        "📜 DayZ Manager Logs",
                        reason="Auto-created for DayZ Manager logs",
                    )
                except discord.Forbidden:
                    category = None

        # Two naming styles are used by your code:
        #  1) "<map>-logs" (Setup cog)
        #  2) "factions-<map>-logs" (faction logs)
        # Here we pick the general map log "<map>-logs" for log_action.
        if map_key:
            base = f"{map_key}-logs"
        else:
            base = "dayz-manager-logs"

        channel = discord.utils.get(guild.text_channels, name=base)
        if channel is None and category is not None:
            try:
                channel = await guild.create_text_channel(
                    base, category=category, reason="Auto-created DayZ Manager map logs"
                )
            except discord.Forbidden:
                channel = None
    except Exception as e:
        print(f"⚠️ Failed resolving logs channel: {e}")

    return channel or guild.system_channel


async def log_action(
    guild: discord.Guild,
    map_key: Optional[str],
    title: str,
    description: str,
    color: int = 0x2B90D9,
) -> None:
    """
    Persist a generic action log and post a simple embed to the map log channel.
    """
    await ensure_connection()

    # Persist
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO action_logs (guild_id, map, title, description, color)
                VALUES ($1,$2,$3,$4,$5)
                """,
                str(guild.id), map_key, title, description, color
            )
    except Exception as e:
        print(f"⚠️ Failed to insert action_logs row: {e}")

    # Post embed
    ch = await _resolve_logs_channel(guild, map_key)
    if ch is None:
        return

    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="DayZ Manager • Logs", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    embed.timestamp = discord.utils.utcnow()

    try:
        await ch.send(embed=embed)
    except discord.Forbidden:
        print("⚠️ Missing permission to send to log channel.")
    except Exception as e:
        print(f"⚠️ Failed to send log embed: {e}")


# ==============================
# 🪵 Faction logging (used by cogs)
# ==============================

async def log_faction_action(
    guild: discord.Guild,
    action: str,
    faction_name: Optional[str],
    user: discord.Member,
    details: str,
    map_key: str,
) -> None:
    """
    Persist a faction action to the DB and post a rich embed to a map-specific
    log channel named 'factions-<map>-logs' (fallback to system channel).
    """
    await ensure_connection()

    mk = (map_key or "").strip().lower()
    full_details = f"[map: {mk}] {details}" if mk else details

    # DB persist
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
                VALUES ($1, $2, $3, $4, $5);
                """,
                str(guild.id), action, faction_name, str(user.id), full_details
            )
    except Exception as e:
        print(f"⚠️ Failed to write faction_logs row: {e}")

    # Resolve a channel in the logs category named factions-<map>-logs
    log_channel: Optional[discord.TextChannel] = None
    try:
        category = discord.utils.get(guild.categories, name="📜 DayZ Manager Logs")
        if category is None:
            try:
                category = await guild.create_category(
                    "📜 DayZ Manager Logs",
                    reason="Auto-created for faction logs"
                )
            except discord.Forbidden:
                category = None

        channel_name = f"factions-{mk}-logs" if mk else "factions-logs"
        log_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if log_channel is None and category is not None:
            try:
                log_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    reason="Auto-created map-specific faction log channel",
                )
                try:
                    scope = mk.title() if mk else "all maps"
                    await log_channel.send(f"🪵 This channel logs faction activity for **{scope}**.")
                except Exception:
                    pass
            except discord.Forbidden:
                log_channel = None
    except Exception as e:
        print(f"⚠️ Error resolving faction log channel: {e}")

    if log_channel is None:
        log_channel = guild.system_channel

    # Build & send embed
    al = (action or "").lower()
    if "create" in al:
        color = 0x2ECC71  # green
    elif "delete" in al or "disband" in al:
        color = 0xE74C3C  # red
    elif "update" in al or "edit" in al:
        color = 0xF1C40F  # yellow
    else:
        color = 0x3498DB  # blue

    embed = discord.Embed(title=f"🪵 {action}", color=color)
    if faction_name:
        embed.add_field(name="🏳️ Faction", value=f"**{faction_name}**", inline=True)
    if mk:
        embed.add_field(name="🗺️ Map", value=mk.title(), inline=True)
    embed.add_field(name="👤 Action By", value=user.mention, inline=True)
    embed.add_field(
        name="🕓 Timestamp",
        value=f"<t:{int(discord.utils.utcnow().timestamp())}:f>",
        inline=False,
    )
    embed.add_field(name="📋 Details", value=details, inline=False)
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.set_footer(text=f"Faction Logs • {guild.name}")
    embed.timestamp = discord.utils.utcnow()

    if log_channel is not None:
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("⚠️ No permission to send to the resolved log channel.")
        except Exception as e:
            print(f"⚠️ Failed to send faction log embed: {e}")
    else:
        print("ℹ️ No available log channel (and no system channel). Embed not sent.")
