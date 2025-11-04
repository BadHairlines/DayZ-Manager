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
    """Ensure a global asyncpg pool exists and core tables are created."""
    global db_pool
    if db_pool is not None:
        return db_pool

    dsn = None
    for key in DEFAULT_DB_ENV_KEYS:
        if os.getenv(key):
            dsn = os.getenv(key)
            break
    if not dsn:
        raise RuntimeError("No database URL found. Set one of: DATABASE_URL, POSTGRES_URL, PG_URL")

    db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flags (
                guild_id TEXT NOT NULL,
                map TEXT NOT NULL,
                flag TEXT NOT NULL,
                status TEXT NOT NULL,
                role_id TEXT,
                PRIMARY KEY (guild_id, map, flag)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flag_messages (
                guild_id TEXT NOT NULL,
                map TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                log_channel_id TEXT,
                PRIMARY KEY (guild_id, map)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS action_logs (
                id BIGSERIAL PRIMARY KEY,
                guild_id TEXT NOT NULL,
                map TEXT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                color INT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
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


async def init_db() -> asyncpg.Pool:
    return await ensure_connection()


# ==============================
# 🗺️ Static game data
# ==============================

FLAGS: List[str] = [
    "Wolf", "APA", "NAPA", "Coyote", "Bear", "Raven", "Boar", "Eagle", "Stag", "Viper"
]

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
    """Upsert a flag row. status is '✅' for unclaimed, '❌' for claimed."""
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
    await set_flag(guild_id, map_key, flag_name, "✅", None)


# ==============================
# 🧾 Embeds & logging
# ==============================

def _split_claims(rows: List[asyncpg.Record]) -> Tuple[List[str], List[Tuple[str, str]]]:
    unclaimed, claimed = [], []
    for r in rows:
        if r["status"] == "✅":
            unclaimed.append(r["flag"])
        else:
            claimed.append((r["flag"], r["role_id"]))
    return unclaimed, claimed


async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    """Build a clean single-list flag ownership embed (classic DayZ Manager style)."""
    await ensure_connection()
    rows = await get_all_flags(guild_id, map_key)

    # seed flags if empty
    if not rows:
        for flag in FLAGS:
            await set_flag(guild_id, map_key, flag, "✅", None)
        rows = await get_all_flags(guild_id, map_key)

    map_info = MAP_DATA.get(map_key, {"name": map_key.title(), "image": None})

    embed = discord.Embed(
        title=f"🏴 Flag Ownership — {map_info['name']}",
        color=0x3498DB
    )

    if map_info.get("image"):
        embed.set_image(url=map_info["image"])

    embed.set_footer(
        text="DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    embed.timestamp = discord.utils.utcnow()

    # sort claimed on top, then unclaimed
    claimed = [r for r in rows if r["role_id"]]
    unclaimed = [r for r in rows if not r["role_id"]]
    ordered = claimed + unclaimed

    lines = []
    for r in ordered:
        flag = r["flag"]
        role_id = r["role_id"]
        if role_id:
            lines.append(f"❌ **{flag}** — <@&{role_id}>")
        else:
            lines.append(f"✅ **{flag}** — *Unclaimed*")

    embed.description = "\n".join(lines) if lines else "_No flags found._"
    return embed

# ==============================
# 🪵 Logging utilities
# ==============================

async def _resolve_logs_channel(guild: discord.Guild, map_key: Optional[str] = None, prefer_category: bool = True) -> Optional[discord.TextChannel]:
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

        base = f"{map_key}-logs" if map_key else "dayz-manager-logs"
        channel = discord.utils.get(guild.text_channels, name=base)
        if channel is None and category is not None:
            channel = await guild.create_text_channel(base, category=category, reason="Auto-created DayZ Manager map logs")
        return channel or guild.system_channel
    except Exception as e:
        print(f"⚠️ Failed resolving logs channel: {e}")
        return guild.system_channel


async def log_action(guild: discord.Guild, map_key: Optional[str], title: str, description: str, color: int = 0x2B90D9) -> None:
    await ensure_connection()
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


async def log_faction_action(guild: discord.Guild, action: str, faction_name: Optional[str], user: discord.Member, details: str, map_key: str) -> None:
    await ensure_connection()

    mk = (map_key or "").strip().lower()
    full_details = f"[map: {mk}] {details}" if mk else details

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

    # Resolve channel
    log_channel = None
    try:
        category = discord.utils.get(guild.categories, name="📜 DayZ Manager Logs")
        if category is None:
            category = await guild.create_category("📜 DayZ Manager Logs", reason="Auto-created for faction logs")

        channel_name = f"factions-{mk}-logs" if mk else "factions-logs"
        log_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if log_channel is None:
            log_channel = await guild.create_text_channel(name=channel_name, category=category, reason="Auto-created map-specific faction log channel")
            await log_channel.send(f"🪵 This channel logs faction activity for **{mk.title() or 'All Maps'}**.")
    except Exception as e:
        print(f"⚠️ Error resolving faction log channel: {e}")
        log_channel = guild.system_channel

    # Pick embed color
    al = (action or "").lower()
    if "create" in al:
        color = 0x2ECC71
    elif "delete" in al or "disband" in al:
        color = 0xE74C3C
    elif "update" in al or "edit" in al:
        color = 0xF1C40F
    else:
        color = 0x3498DB

    embed = discord.Embed(title=f"🪵 {action}", color=color)
    if faction_name:
        embed.add_field(name="🏳️ Faction", value=f"**{faction_name}**", inline=True)
    if mk:
        embed.add_field(name="🗺️ Map", value=mk.title(), inline=True)
    embed.add_field(name="👤 Action By", value=user.mention, inline=True)
    embed.add_field(name="🕓 Timestamp", value=f"<t:{int(discord.utils.utcnow().timestamp())}:f>", inline=False)
    embed.add_field(name="📋 Details", value=details, inline=False)
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.set_footer(text=f"Faction Logs • {guild.name}")
    embed.timestamp = discord.utils.utcnow()

    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("⚠️ No permission to send to the resolved log channel.")
        except Exception as e:
            print(f"⚠️ Failed to send faction log embed: {e}")
