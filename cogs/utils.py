from __future__ import annotations

import contextlib
import os
from typing import Any, AsyncIterator, Optional

import asyncpg
import discord

db_pool: Optional[asyncpg.Pool] = None

FLAGS: list[str] = [
    "APA", "Altis", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals",
    "CHEL", "Chedaki", "CMC", "Crook", "DayZ", "HunterZ", "NAPA",
    "NSahrani", "Pirates", "Rex", "Refuge", "Rooster", "RSTA", "Snake",
    "TEC", "UEC", "Wolf", "Zagorky", "Zenit",
]

FLAG_LOOKUP = {flag.casefold(): flag for flag in FLAGS}

MAP_DATA: dict[str, dict[str, Any]] = {
    "livonia": {
        "name": "Livonia",
        "image": "https://i.postimg.cc/QN9vfr9m/Livonia.jpg",
    },
    "chernarus": {
        "name": "Chernarus",
        "image": "https://i.postimg.cc/3RWzMsLK/Chernarus.jpg",
    },
    "sakhal": {
        "name": "Sakhal",
        "image": "https://i.postimg.cc/HkBSpS8j/Sakhal.png",
    },
}

FOOTER_ICON = "https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"


def normalize_map(value: str) -> str:
    value = str(value or "").strip().casefold()
    aliases = {
        "livonia": "livonia",
        "chernarus": "chernarus",
        "chernarusplus": "chernarus",
        "chernarus plus": "chernarus",
        "sakhal": "sakhal",
    }
    return aliases.get(value, value)


def normalize_flag(value: str) -> Optional[str]:
    if not value:
        return None
    return FLAG_LOOKUP.get(str(value).strip().casefold())


def normalize_server(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def channel_name_for(map_key: str, server: str) -> str:
    raw = f"flags-{normalize_map(map_key)}-{normalize_server(server)}"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-")[:100] or "flags"


async def ensure_connection() -> asyncpg.Pool:
    global db_pool

    if db_pool is not None:
        try:
            if not db_pool._closed:
                return db_pool
        except AttributeError:
            pass

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable is missing.")

    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]

    db_pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=int(os.getenv("DB_MAX_POOL_SIZE", "10")),
        command_timeout=30,
        max_inactive_connection_lifetime=300,
    )

    async with db_pool.acquire() as conn:
        await migrate(conn)

    return db_pool


async def migrate(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS flags (
            guild_id TEXT NOT NULL,
            map TEXT NOT NULL,
            server TEXT NOT NULL DEFAULT 'server 1',
            flag TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '✅',
            role_id TEXT,
            PRIMARY KEY (guild_id, map, server, flag)
        );
    """)

    flag_columns = {
        row["column_name"]
        for row in await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'flags'
        """)
    }

    if "server" not in flag_columns:
        await conn.execute("""
            ALTER TABLE flags
            ADD COLUMN server TEXT NOT NULL DEFAULT 'server 1'
        """)
        await conn.execute("ALTER TABLE flags DROP CONSTRAINT IF EXISTS flags_pkey")
        await conn.execute("""
            ALTER TABLE flags
            ADD PRIMARY KEY (guild_id, map, server, flag)
        """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS flag_messages (
            guild_id TEXT NOT NULL,
            map TEXT NOT NULL,
            server TEXT NOT NULL DEFAULT 'server 1',
            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            log_channel_id TEXT,
            PRIMARY KEY (guild_id, map, server)
        );
    """)

    message_columns = {
        row["column_name"]
        for row in await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'flag_messages'
        """)
    }

    if "server" not in message_columns:
        await conn.execute("""
            ALTER TABLE flag_messages
            ADD COLUMN server TEXT NOT NULL DEFAULT 'server 1'
        """)
        await conn.execute(
            "ALTER TABLE flag_messages DROP CONSTRAINT IF EXISTS flag_messages_pkey"
        )
        await conn.execute("""
            ALTER TABLE flag_messages
            ADD PRIMARY KEY (guild_id, map, server)
        """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_flags_lookup
        ON flags (guild_id, map, server)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_flag_messages_guild
        ON flag_messages (guild_id)
    """)


@contextlib.asynccontextmanager
async def safe_acquire() -> AsyncIterator[asyncpg.Connection]:
    pool = await ensure_connection()
    async with pool.acquire() as conn:
        yield conn


async def close_db() -> None:
    global db_pool
    if db_pool is not None:
        await db_pool.close()
        db_pool = None


async def get_flag(guild_id: str, map_key: str, server: str, flag: str):
    canonical = normalize_flag(flag)
    if not canonical:
        return None

    async with safe_acquire() as conn:
        return await conn.fetchrow("""
            SELECT guild_id, map, server, flag, status, role_id
            FROM flags
            WHERE guild_id=$1 AND map=$2 AND server=$3 AND flag=$4
        """, str(guild_id), normalize_map(map_key), normalize_server(server), canonical)


async def get_all_flags(guild_id: str, map_key: str, server: str):
    async with safe_acquire() as conn:
        return await conn.fetch("""
            SELECT guild_id, map, server, flag, status, role_id
            FROM flags
            WHERE guild_id=$1 AND map=$2 AND server=$3
            ORDER BY flag ASC
        """, str(guild_id), normalize_map(map_key), normalize_server(server))


async def initialize_flags(guild_id: str, map_key: str, server: str) -> None:
    async with safe_acquire() as conn:
        await conn.executemany("""
            INSERT INTO flags (guild_id, map, server, flag, status, role_id)
            VALUES ($1, $2, $3, $4, '✅', NULL)
            ON CONFLICT (guild_id, map, server, flag) DO NOTHING
        """, [
            (str(guild_id), normalize_map(map_key), normalize_server(server), flag)
            for flag in FLAGS
        ])


async def claim_flag(
    guild_id: str,
    map_key: str,
    server: str,
    flag: str,
    role_id: str,
):
    canonical = normalize_flag(flag)
    if not canonical:
        return None

    async with safe_acquire() as conn:
        return await conn.fetchrow("""
            UPDATE flags
            SET status='❌', role_id=$5
            WHERE guild_id=$1
              AND map=$2
              AND server=$3
              AND flag=$4
              AND status='✅'
              AND role_id IS NULL
            RETURNING *
        """, str(guild_id), normalize_map(map_key), normalize_server(server),
             canonical, str(role_id))


async def release_flag(guild_id: str, map_key: str, server: str, flag: str):
    canonical = normalize_flag(flag)
    if not canonical:
        return None

    async with safe_acquire() as conn:
        return await conn.fetchrow("""
            UPDATE flags
            SET status='✅', role_id=NULL
            WHERE guild_id=$1
              AND map=$2
              AND server=$3
              AND flag=$4
              AND status='❌'
              AND role_id IS NOT NULL
            RETURNING *
        """, str(guild_id), normalize_map(map_key), normalize_server(server), canonical)


async def save_flag_message(
    guild_id: str,
    map_key: str,
    server: str,
    channel_id: str,
    message_id: str,
) -> None:
    async with safe_acquire() as conn:
        await conn.execute("""
            INSERT INTO flag_messages (
                guild_id, map, server, channel_id, message_id
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, map, server)
            DO UPDATE SET
                channel_id=EXCLUDED.channel_id,
                message_id=EXCLUDED.message_id
        """, str(guild_id), normalize_map(map_key), normalize_server(server),
             str(channel_id), str(message_id))


async def get_flag_message(guild_id: str, map_key: str, server: str):
    async with safe_acquire() as conn:
        return await conn.fetchrow("""
            SELECT channel_id, message_id
            FROM flag_messages
            WHERE guild_id=$1 AND map=$2 AND server=$3
        """, str(guild_id), normalize_map(map_key), normalize_server(server))


async def get_flag_sessions(guild_id: str):
    async with safe_acquire() as conn:
        return await conn.fetch("""
            SELECT map, server, channel_id, message_id
            FROM flag_messages
            WHERE guild_id=$1
            ORDER BY map, server
        """, str(guild_id))


def flag_emoji(guild: discord.Guild | None, flag: str) -> str:
    if guild:
        custom = discord.utils.get(guild.emojis, name=flag)
        if custom:
            return f"{custom} "
    return ""


async def create_flag_embed(
    guild_id: str,
    map_key: str,
    server: str,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    map_key = normalize_map(map_key)
    server = normalize_server(server)

    rows = await get_all_flags(guild_id, map_key, server)
    map_info = MAP_DATA.get(map_key, {"name": map_key.title(), "image": None})

    claimed = [row for row in rows if row["role_id"]]
    unclaimed = [row for row in rows if not row["role_id"]]

    embed = discord.Embed(
        title=f"🏴 Flag Ownership — {map_info['name']}",
        description=f"**Server:** `{server}`",
        color=0x3498DB,
    )

    if map_info.get("image"):
        embed.set_image(url=map_info["image"])

    lines: list[str] = []

    for row in claimed:
        lines.append(
            f"{flag_emoji(guild, row['flag'])}❌ **{row['flag']}** — <@&{row['role_id']}>"
        )

    for row in unclaimed:
        lines.append(
            f"{flag_emoji(guild, row['flag'])}✅ **{row['flag']}** — *Unclaimed*"
        )

    if not lines:
        embed.add_field(name="Flags", value="_No flags found._", inline=False)
    else:
        chunks: list[str] = []
        current = ""

        for line in lines:
            if len(current) + len(line) + 1 > 1024:
                chunks.append(current.rstrip())
                current = ""
            current += line + "\n"

        if current:
            chunks.append(current.rstrip())

        for index, chunk in enumerate(chunks):
            embed.add_field(
                name="Flags" if index == 0 else f"Flags — Continued {index + 1}",
                value=chunk,
                inline=False,
            )

    embed.set_footer(text="DayZ Manager", icon_url=FOOTER_ICON)
    embed.timestamp = discord.utils.utcnow()
    return embed


async def refresh_flag_embed(
    bot: discord.Client,
    guild_id: str,
    map_key: str,
    server: str,
) -> bool:
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return False

    row = await get_flag_message(guild_id, map_key, server)
    if not row:
        return False

    channel = guild.get_channel(int(row["channel_id"]))
    if not isinstance(channel, discord.TextChannel):
        return False

    try:
        message = await channel.fetch_message(int(row["message_id"]))
        embed = await create_flag_embed(guild_id, map_key, server, guild)
        await message.edit(embed=embed)
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False
