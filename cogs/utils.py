
Action: file_editor create /app/patched/cogs/utils.py --file-text "from __future__ import annotations

import os
import asyncio
import contextlib
from typing import Optional, List, Dict, Any, AsyncIterator

import asyncpg
import discord


# -----------------------------
# DB STATE
# -----------------------------
db_pool: Optional[asyncpg.Pool] = None
_pool_lock: asyncio.Lock = asyncio.Lock()


def _pool_alive(pool: Optional[asyncpg.Pool]) -> bool:
    \"\"\"Safe check that doesn't rely on private attrs breaking across versions.\"\"\"
    if pool is None:
        return False
    closed = getattr(pool, \"_closed\", False)
    return not closed


# -----------------------------
# CONNECTION
# -----------------------------
async def ensure_connection() -> asyncpg.Pool:
    \"\"\"Ensure DB pool exists and core tables are initialized.\"\"\"
    global db_pool

    if _pool_alive(db_pool):
        return db_pool  # type: ignore[return-value]

    async with _pool_lock:
        # double-checked: another coroutine may have created the pool while we waited
        if _pool_alive(db_pool):
            return db_pool  # type: ignore[return-value]

        dsn = os.getenv(\"DATABASE_URL\")
        if not dsn:
            raise RuntimeError(\"DATABASE_URL missing\")

        if dsn.startswith(\"postgres://\"):
            dsn = dsn.replace(\"postgres://\", \"postgresql://\", 1)

        db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

        async with db_pool.acquire() as conn:
            await conn.execute(\"\"\"
                CREATE TABLE IF NOT EXISTS flags (
                    guild_id TEXT NOT NULL,
                    map TEXT NOT NULL,
                    flag TEXT NOT NULL,
                    status TEXT NOT NULL,
                    role_id TEXT,
                    PRIMARY KEY (guild_id, map, flag)
                );
            \"\"\")

            await conn.execute(\"\"\"
                CREATE TABLE IF NOT EXISTS flag_messages (
                    guild_id TEXT NOT NULL,
                    map TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    log_channel_id TEXT,
                    PRIMARY KEY (guild_id, map)
                );
            \"\"\")

    return db_pool  # type: ignore[return-value]


@contextlib.asynccontextmanager
async def safe_acquire() -> AsyncIterator[asyncpg.Connection]:
    \"\"\"Safely acquire a DB connection from the pool.\"\"\"
    pool = await ensure_connection()
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)


async def close_db() -> None:
    \"\"\"Close DB pool cleanly.\"\"\"
    global db_pool

    if _pool_alive(db_pool):
        await db_pool.close()  # type: ignore[union-attr]
    db_pool = None


# -----------------------------
# CONSTANTS
# -----------------------------
FLAGS: List[str] = [
    \"APA\", \"Altis\", \"BabyDeer\", \"Bear\", \"Bohemia\", \"BrainZ\", \"Cannibals\",
    \"CHEL\", \"Chedaki\", \"CMC\", \"Crook\", \"HunterZ\", \"NAPA\", \"NSahrani\",
    \"Pirates\", \"Rex\", \"Refuge\", \"Rooster\", \"RSTA\", \"Snake\",
    \"TEC\", \"UEC\", \"Wolf\", \"Zagorky\", \"Zenit\",
]

# O(1) case-insensitive lookup
_FLAG_CANON: Dict[str, str] = {f.lower(): f for f in FLAGS}


def canonical_flag(raw: str) -> Optional[str]:
    \"\"\"Return canonical flag name (case-insensitive) or None if unknown.\"\"\"
    if not raw:
        return None
    return _FLAG_CANON.get(raw.strip().lower())


MAP_DATA: Dict[str, Dict[str, Any]] = {
    \"livonia\": {
        \"name\": \"Livonia\",
        \"image\": \"https://i.postimg.cc/QN9vfr9m/Livonia.jpg\",
    },
    \"chernarus\": {
        \"name\": \"Chernarus\",
        \"image\": \"https://i.postimg.cc/3RWzMsLK/Chernarus.jpg\",
    },
    \"sakhal\": {
        \"name\": \"Sakhal\",
        \"image\": \"https://i.postimg.cc/HkBSpS8j/Sakhal.png\",
    },
}


# -----------------------------
# DB OPERATIONS
# -----------------------------
async def get_flag(guild_id: str, map_key: str, flag: str):
    async with safe_acquire() as conn:
        return await conn.fetchrow(
            \"SELECT * FROM flags WHERE guild_id=$1 AND map=$2 AND flag=$3\",
            guild_id, map_key, flag,
        )


async def get_all_flags(guild_id: str, map_key: str):
    async with safe_acquire() as conn:
        return await conn.fetch(
            \"SELECT * FROM flags WHERE guild_id=$1 AND map=$2 ORDER BY flag ASC\",
            guild_id, map_key,
        )


async def set_flag(
    guild_id: str,
    map_key: str,
    flag: str,
    status: str,
    role_id: Optional[str],
) -> None:
    \"\"\"Insert or update a flag. All identifiers must be strings.\"\"\"
    # guard against silent int-as-text errors
    guild_id = str(guild_id)
    if role_id is not None:
        role_id = str(role_id)

    async with safe_acquire() as conn:
        await conn.execute(
            \"\"\"
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET
                status = EXCLUDED.status,
                role_id = EXCLUDED.role_id
            \"\"\",
            guild_id, map_key, flag, status, role_id,
        )


async def release_flag(guild_id: str, map_key: str, flag: str) -> None:
    await set_flag(guild_id, map_key, flag, \"✅\", None)


# -----------------------------
# EMBED BUILDER (PURE UI LAYER)
# -----------------------------
async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    \"\"\"Build flag ownership embed (UI only).\"\"\"
    guild_id = str(guild_id)

    rows = await get_all_flags(guild_id, map_key)

    # Auto-seed if empty
    if not rows:
        for flag in FLAGS:
            await set_flag(guild_id, map_key, flag, \"✅\", None)
        rows = await get_all_flags(guild_id, map_key)

    map_info = MAP_DATA.get(
        map_key,
        {\"name\": map_key.title(), \"image\": None},
    )

    embed = discord.Embed(
        title=f\"🏴 Flag Ownership — {map_info['name']}\",
        color=0x3498DB,
    )

    if map_info[\"image\"]:
        embed.set_image(url=map_info[\"image\"])

    embed.set_footer(
        text=\"DayZ Manager\",
        icon_url=\"https://i.postimg.cc/rmXpLFpv/ewn60cg6.png\",
    )
    embed.timestamp = discord.utils.utcnow()

    # Order: claimed first, then unclaimed
    claimed = [r for r in rows if r[\"role_id\"]]
    unclaimed = [r for r in rows if not r[\"role_id\"]]

    lines = []
    for r in (claimed + unclaimed):
        if r[\"role_id\"]:
            lines.append(f\"❌ **{r['flag']}** — <@&{r['role_id']}>\")
        else:
            lines.append(f\"✅ **{r['flag']}** — *Unclaimed*\")

    embed.description = \"\n\".join(lines) if lines else \"_No flags found_\"

    return embed


async def refresh_flag_message(bot, guild_id: str, map_key: str, view=None) -> None:
    \"\"\"
    Re-render the pinned flag message for a guild/map.
    Safe to call from any command or UI callback.
    \"\"\"
    guild_id = str(guild_id)

    async with safe_acquire() as conn:
        row = await conn.fetchrow(
            \"SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2\",
            guild_id, map_key,
        )

    if not row:
        return

    channel = bot.get_channel(int(row[\"channel_id\"]))
    if channel is None:
        return

    try:
        msg = await channel.fetch_message(int(row[\"message_id\"]))
    except discord.NotFound:
        return

    embed = await create_flag_embed(guild_id, map_key)
    if view is not None:
        await msg.edit(embed=embed, view=view)
    else:
        await msg.edit(embed=embed)
"
Observation: Create successful: /app/patched/cogs/utils.py
