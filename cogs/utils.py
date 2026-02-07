from __future__ import annotations

import os
import asyncio
import logging
from typing import Optional, List, Dict, Any, AsyncIterator
import asyncpg
import discord
import contextlib

# ------------------------------
# 🔧 Logging Setup
# ------------------------------
logger = logging.getLogger("dayz_manager")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# ------------------------------
# 🔌 Database pool & bootstrap
# ------------------------------

db_pool: Optional[asyncpg.Pool] = None


async def ensure_connection(retries: int = 3, delay: float = 2.0) -> asyncpg.Pool:
    """Ensure a global asyncpg pool exists and core tables are created."""
    global db_pool

    if db_pool and not db_pool._closed:
        return db_pool

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("❌ DATABASE_URL not set — please define it in your environment.")

    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)

    for attempt in range(retries):
        try:
            db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
            break
        except Exception as e:
            logger.warning(f"DB connection failed (attempt {attempt+1}/{retries}): {e}")
            await asyncio.sleep(delay)
    else:
        raise RuntimeError("❌ Could not connect to the database after retries.")

    async with db_pool.acquire() as conn:
        # Create tables if missing
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

    logger.info("✅ Database connected and tables ensured.")
    return db_pool


@contextlib.asynccontextmanager
async def safe_acquire() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a DB connection safely with auto-reconnect."""
    await ensure_connection()
    conn = await db_pool.acquire()
    try:
        yield conn
    finally:
        await db_pool.release(conn)


async def close_db() -> None:
    """Gracefully close the global DB pool."""
    global db_pool
    if db_pool and not db_pool._closed:
        await db_pool.close()
        db_pool = None
        logger.info("✅ Database pool closed.")


# ------------------------------
# 🗺️ Static game data
# ------------------------------

FLAGS: List[str] = [
    "APA", "Altis", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals",
    "CHEL", "Chedaki", "CMC", "Crook", "HunterZ", "NAPA", "NSahrani",
    "Pirates", "Rex", "Refuge", "Rooster", "RSTA", "Snake",
    "TEC", "UEC", "Wolf", "Zagorky", "Zenit"
]

MAP_DATA: Dict[str, Dict[str, Any]] = {
    "livonia": {"name": "Livonia", "image": "https://i.postimg.cc/QN9vfr9m/Livonia.jpg"},
    "chernarus": {"name": "Chernarus", "image": "https://i.postimg.cc/3RWzMsLK/Chernarus.jpg"},
    "sakhal": {"name": "Sakhal", "image": "https://i.postimg.cc/HkBSpS8j/Sakhal.png"},
}

# ------------------------------
# 🏴 Flag helpers with caching
# ------------------------------

_flag_cache: Dict[str, List[asyncpg.Record]] = {}


async def get_flag(guild_id: str, map_key: str, flag_name: str) -> Optional[asyncpg.Record]:
    async with safe_acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM flags WHERE guild_id=$1 AND map=$2 AND flag=$3",
            guild_id, map_key, flag_name
        )


async def get_all_flags(guild_id: str, map_key: str, refresh: bool = False) -> List[asyncpg.Record]:
    cache_key = f"{guild_id}:{map_key}"
    if not refresh and cache_key in _flag_cache:
        return _flag_cache[cache_key]

    async with safe_acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM flags WHERE guild_id=$1 AND map=$2 ORDER BY flag ASC",
            guild_id, map_key
        )
    _flag_cache[cache_key] = list(rows)
    return _flag_cache[cache_key]


async def set_flag(
    guild_id: str,
    map_key: str,
    flag_name: str,
    status: str,
    role_id: Optional[str]
) -> None:
    """Upsert a flag row."""
    async with safe_acquire() as conn:
        await conn.execute(
            """
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET status=EXCLUDED.status, role_id=EXCLUDED.role_id
            """,
            guild_id, map_key, flag_name, status, role_id
        )
    # Refresh cache
    await get_all_flags(guild_id, map_key, refresh=True)


async def release_flag(guild_id: str, map_key: str, flag_name: str) -> None:
    await set_flag(guild_id, map_key, flag_name, "✅", None)


# ------------------------------
# 🧾 Embeds & flag list
# ------------------------------

async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    """Create a clean flag ownership embed."""
    rows = await get_all_flags(guild_id, map_key)
    if not rows:
        for flag in FLAGS:
            await set_flag(guild_id, map_key, flag, "✅", None)
        rows = await get_all_flags(guild_id, map_key)

    map_info = MAP_DATA.get(map_key, {"name": map_key.title(), "image": None})
    embed = discord.Embed(title=f"🏴 Flag Ownership — {map_info['name']}", color=0x3498DB)
    if map_info.get("image"):
        embed.set_image(url=map_info["image"])
    embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    embed.timestamp = discord.utils.utcnow()

    claimed, unclaimed = [r for r in rows if r["role_id"]], [r for r in rows if not r["role_id"]]
    lines = [f"❌ **{r['flag']}** — <@&{r['role_id']}>" for r in claimed] + \
            [f"✅ **{r['flag']}** — *Unclaimed*" for r in unclaimed]

    embed.description = "\n".join(lines) if lines else "_No flags found._"
    return embed


# ------------------------------
# 🪵 Logging & channel helpers
# ------------------------------

async def _ensure_category(guild: discord.Guild) -> Optional[discord.CategoryChannel]:
    cat = discord.utils.get(guild.categories, name="📜 DayZ Manager Logs")
    if cat:
        return cat
    try:
        return await guild.create_category("📜 DayZ Manager Logs", reason="Auto-created for DayZ Manager logs")
    except discord.Forbidden:
        logger.warning(f"No permission to create logs category in {guild.name}")
        return None


async def _resolve_logs_channel(guild: discord.Guild, map_key: Optional[str] = None) -> Optional[discord.TextChannel]:
    cat = await _ensure_category(guild)
    name = f"flaglogs-{map_key}" if map_key else "dayz-manager-logs"
    channel = discord.utils.get(guild.text_channels, name=name)
    if channel:
        return channel
    if cat:
        try:
            channel = await guild.create_text_channel(name, category=cat, reason="Auto-created logs channel")
            await channel.send(f"🗒️ Logs for **{map_key.title() if map_key else 'All Maps'}** initialized.")
            return channel
        except discord.Forbidden:
            logger.warning(f"No permission to create logs channel in {guild.name}")
    return guild.system_channel


async def _resolve_faction_logs_channel(guild: discord.Guild, map_key: Optional[str] = None) -> Optional[discord.TextChannel]:
    cat = await _ensure_category(guild)
    mk = (map_key or "").strip().lower()
    name = f"factionlogs-{mk}" if mk else "faction-logs"
    channel = discord.utils.get(guild.text_channels, name=name)
    if channel:
        return channel
    if cat:
        try:
            channel = await guild.create_text_channel(name, category=cat, reason="Auto-created faction logs")
            await channel.send(f"🗒️ Faction logs for **{mk.title() if mk else 'All Maps'}** initialized.")
            return channel
        except discord.Forbidden:
            logger.warning(f"No permission to create faction logs channel in {guild.name}")
    return guild.system_channel


async def log_action(
    guild: discord.Guild,
    map_key: Optional[str],
    title: str,
    description: str,
    color: int = 0x2B90D9
) -> None:
    """Log an action to DB and Discord."""
    try:
        async with safe_acquire() as conn:
            await conn.execute(
                "INSERT INTO action_logs (guild_id, map, title, description, color) VALUES ($1,$2,$3,$4,$5)",
                str(guild.id), map_key, title, description, color
            )
    except Exception as e:
        logger.error(f"Failed to insert action_logs row: {e}")

    ch = await _resolve_logs_channel(guild, map_key)
    if ch:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="DayZ Manager • Logs", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        try:
            await ch.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send log embed: {e}")


def _prettify_details(details: str) -> str:
    parts = [p.strip() for p in details.split(",") if p.strip()]
    filtered = [p for p in parts if not p.lower().startswith("map:")]
    return "\n".join(filtered) if filtered else details


async def log_faction_action(
    guild: discord.Guild,
    action: str,
    faction_name: Optional[str],
    user: discord.Member,
    details: str,
    map_key: str,
) -> None:
    """Log faction actions both to DB and Discord with auto-created channels."""
    mk = (map_key or "").strip().lower()
    full_details = f"[map: {mk}] {details}" if mk else details

    try:
        async with safe_acquire() as conn:
            await conn.execute(
                "INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details) VALUES ($1,$2,$3,$4,$5)",
                str(guild.id), action, faction_name, str(user.id), full_details
            )
    except Exception as e:
        logger.error(f"Failed to write faction_logs row: {e}")

    log_channel = await _resolve_faction_logs_channel(guild, mk)
    if not log_channel:
        logger.info(f"No faction log channel available for {guild.name}/{mk}")
        return

    color_map = {
        "create": 0x2ECC71,
        "created": 0x2ECC71,
        "delete": 0xE74C3C,
        "disband": 0xE74C3C,
        "removed": 0xE74C3C,
        "update": 0xF1C40F,
        "edit": 0xF1C40F,
        "member": 0x9B59B6,
    }
    color = next((c for k, c in color_map.items() if k in action.lower()), 0x3498DB)

    embed = discord.Embed(title=f"🪵 {action}", color=color)
    if faction_name:
        embed.add_field(name="🏳️ Faction", value=f"**{faction_name}**", inline=True)
    if mk:
        embed.add_field(name="🗺️ Map", value=mk.title(), inline=True)
    embed.add_field(name="👤 Action By", value=user.mention, inline=True)
    embed.add_field(name="📋 Details", value=_prettify_details(details), inline=False)
    embed.add_field(name="🕓 Timestamp", value=f"<t:{int(discord.utils.utcnow().timestamp())}:f>", inline=False)
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.set_footer(text=f"Faction Logs • {guild.name}")
    embed.timestamp = discord.utils.utcnow()

    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to send faction log embed: {e}")
