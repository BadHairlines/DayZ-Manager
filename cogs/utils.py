from __future__ import annotations

import os
import contextlib
from typing import Optional, List, Dict, Any, AsyncIterator

import asyncpg
import discord


# =========================================================
# DATABASE STATE
# =========================================================

db_pool: Optional[asyncpg.Pool] = None


# =========================================================
# FLAGS
# =========================================================

FLAGS: List[str] = [
    "APA",
    "Altis",
    "BabyDeer",
    "Bear",
    "Bohemia",
    "BrainZ",
    "Cannibals",
    "CHEL",
    "Chedaki",
    "CMC",
    "Crook",
    "DayZ",
    "HunterZ",
    "NAPA",
    "NSahrani",
    "Pirates",
    "Rex",
    "Refuge",
    "Rooster",
    "RSTA",
    "Snake",
    "TEC",
    "UEC",
    "Wolf",
    "Zagorky",
    "Zenit",
]

FLAG_LOOKUP: Dict[str, str] = {
    flag.lower(): flag
    for flag in FLAGS
}


# =========================================================
# MAPS
# =========================================================

MAP_DATA: Dict[str, Dict[str, Any]] = {
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


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_map(map_key: str) -> str:
    """
    Normalize a DayZ map name.

    Examples:
        Livonia        -> livonia
        LIVONIA        -> livonia
        ChernarusPlus  -> chernarus
        Chernarus Plus -> chernarus
        Sakhal         -> sakhal
    """

    if not map_key:
        return ""

    value = str(map_key).strip().lower()

    aliases = {
        "livonia": "livonia",
        "chernarus": "chernarus",
        "chernarusplus": "chernarus",
        "chernarus plus": "chernarus",
        "sakhal": "sakhal",
    }

    return aliases.get(value, value)


def normalize_flag(flag: str) -> Optional[str]:

    if not flag:
        return None

    return FLAG_LOOKUP.get(
        str(flag).strip().lower()
    )


def normalize_server(server: str) -> str:
    """
    Normalize a server identifier.

    Example:
        "Livonia #1" -> "livonia #1"
        "  Server   2 " -> "server 2"
    """

    return " ".join(
        str(server).strip().lower().split()
    )


# =========================================================
# DATABASE CONNECTION
# =========================================================

async def ensure_connection() -> asyncpg.Pool:

    global db_pool

    if db_pool and not db_pool._closed:
        return db_pool

    dsn = os.getenv("DATABASE_URL")

    if not dsn:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing."
        )

    if dsn.startswith("postgres://"):
        dsn = dsn.replace(
            "postgres://",
            "postgresql://",
            1
        )

    db_pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )

    async with db_pool.acquire() as conn:

        # =====================================================
        # FLAGS TABLE
        # =====================================================

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flags (
                guild_id TEXT NOT NULL,
                map TEXT NOT NULL,
                server TEXT NOT NULL DEFAULT 'server 1',
                flag TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '✅',
                role_id TEXT,

                PRIMARY KEY (
                    guild_id,
                    map,
                    server,
                    flag
                )
            );
        """)

        # =====================================================
        # MIGRATE FLAGS TABLE
        # =====================================================

        columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'flags'
        """)

        column_names = {
            row["column_name"]
            for row in columns
        }

        if "server" not in column_names:

            await conn.execute("""
                ALTER TABLE flags
                ADD COLUMN server TEXT
                NOT NULL DEFAULT 'server 1'
            """)

            await conn.execute("""
                ALTER TABLE flags
                DROP CONSTRAINT IF EXISTS flags_pkey
            """)

            await conn.execute("""
                ALTER TABLE flags
                ADD PRIMARY KEY (
                    guild_id,
                    map,
                    server,
                    flag
                )
            """)

        # =====================================================
        # FLAG MESSAGES
        # =====================================================

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flag_messages (
                guild_id TEXT NOT NULL,
                map TEXT NOT NULL,
                server TEXT NOT NULL DEFAULT 'server 1',
                channel_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                log_channel_id TEXT,

                PRIMARY KEY (
                    guild_id,
                    map,
                    server
                )
            );
        """)

        # =====================================================
        # MIGRATE FLAG MESSAGES
        # =====================================================

        message_columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'flag_messages'
        """)

        message_column_names = {
            row["column_name"]
            for row in message_columns
        }

        if "server" not in message_column_names:

            await conn.execute("""
                ALTER TABLE flag_messages
                ADD COLUMN server TEXT
                NOT NULL DEFAULT 'server 1'
            """)

            await conn.execute("""
                ALTER TABLE flag_messages
                DROP CONSTRAINT IF EXISTS flag_messages_pkey
            """)

            await conn.execute("""
                ALTER TABLE flag_messages
                ADD PRIMARY KEY (
                    guild_id,
                    map,
                    server
                )
            """)

    return db_pool


@contextlib.asynccontextmanager
async def safe_acquire() -> AsyncIterator[asyncpg.Connection]:

    pool = await ensure_connection()

    conn = await pool.acquire()

    try:
        yield conn
    finally:
        await pool.release(conn)


async def close_db() -> None:

    global db_pool

    if db_pool and not db_pool._closed:

        await db_pool.close()

        db_pool = None


# =========================================================
# FLAG OPERATIONS
# =========================================================

async def get_flag(
    guild_id: str,
    map_key: str,
    server: str,
    flag: str,
):

    map_key = normalize_map(map_key)
    server = normalize_server(server)

    canonical = normalize_flag(flag)

    if not canonical:
        return None

    async with safe_acquire() as conn:

        return await conn.fetchrow(
            """
            SELECT *
            FROM flags

            WHERE guild_id = $1
              AND map = $2
              AND server = $3
              AND flag = $4
            """,
            str(guild_id),
            map_key,
            server,
            canonical,
        )


async def get_all_flags(
    guild_id: str,
    map_key: str,
    server: str,
):

    map_key = normalize_map(map_key)
    server = normalize_server(server)

    async with safe_acquire() as conn:

        return await conn.fetch(
            """
            SELECT *
            FROM flags

            WHERE guild_id = $1
              AND map = $2
              AND server = $3

            ORDER BY flag ASC
            """,
            str(guild_id),
            map_key,
            server,
        )


async def set_flag(
    guild_id: str,
    map_key: str,
    server: str,
    flag: str,
    status: str,
    role_id: Optional[str],
) -> None:

    map_key = normalize_map(map_key)
    server = normalize_server(server)

    canonical = normalize_flag(flag)

    if not canonical:
        raise ValueError(
            f"Invalid flag: {flag}"
        )

    async with safe_acquire() as conn:

        await conn.execute(
            """
            INSERT INTO flags (
                guild_id,
                map,
                server,
                flag,
                status,
                role_id
            )

            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6
            )

            ON CONFLICT (
                guild_id,
                map,
                server,
                flag
            )

            DO UPDATE SET
                status = EXCLUDED.status,
                role_id = EXCLUDED.role_id
            """,
            str(guild_id),
            map_key,
            server,
            canonical,
            status,
            role_id,
        )


async def release_flag(
    guild_id: str,
    map_key: str,
    server: str,
    flag: str,
) -> None:

    await set_flag(
        guild_id,
        map_key,
        server,
        flag,
        "✅",
        None,
    )


# =========================================================
# FLAG EMBED
# =========================================================

async def create_flag_embed(
    guild_id: str,
    map_key: str,
    server: str,
    guild: Optional[discord.Guild] = None,
) -> discord.Embed:

    map_key = normalize_map(map_key)
    server = normalize_server(server)

    rows = await get_all_flags(
        guild_id,
        map_key,
        server,
    )

    map_info = MAP_DATA.get(
        map_key,
        {
            "name": map_key.title(),
            "image": None,
        },
    )

    embed = discord.Embed(
        title=(
            f"🏴 Flag Ownership — "
            f"{map_info['name']}"
        ),
        description=(
            f"**Server:** `{server}`"
        ),
        color=0x3498DB,
    )

    if map_info.get("image"):
        embed.set_image(
            url=map_info["image"]
        )

    claimed = []
    unclaimed = []

    for row in rows:

        if row["role_id"]:
            claimed.append(row)
        else:
            unclaimed.append(row)

    lines: List[str] = []

    # =====================================================
    # CLAIMED FLAGS
    # =====================================================

    for row in claimed:

        emoji = ""

        if guild:

            custom_emoji = discord.utils.get(
                guild.emojis,
                name=row["flag"],
            )

            if custom_emoji:
                emoji = f"{custom_emoji} "

        lines.append(
            f"{emoji}❌ **{row['flag']}** — "
            f"<@&{row['role_id']}>"
        )

    # =====================================================
    # UNCLAIMED FLAGS
    # =====================================================

    for row in unclaimed:

        emoji = ""

        if guild:

            custom_emoji = discord.utils.get(
                guild.emojis,
                name=row["flag"],
            )

            if custom_emoji:
                emoji = f"{custom_emoji} "

        lines.append(
            f"{emoji}✅ **{row['flag']}** — "
            f"*Unclaimed*"
        )

    # =====================================================
    # EMBED FIELDS
    # =====================================================

    if not lines:

        embed.add_field(
            name="Flags",
            value="_No flags found_",
            inline=False,
        )

    else:

        chunks = []
        current = ""

        for line in lines:

            if len(current) + len(line) + 1 > 1000:

                chunks.append(current)
                current = ""

            current += line + "\n"

        if current:
            chunks.append(current)

        for index, chunk in enumerate(chunks):

            embed.add_field(
                name=(
                    "Flags"
                    if index == 0
                    else "Flags — Continued"
                ),
                value=chunk.rstrip(),
                inline=False,
            )

    # =====================================================
    # FOOTER
    # =====================================================

    embed.set_footer(
        text="DayZ Manager",
        icon_url=(
            "https://i.postimg.cc/"
            "rmXpLFpv/ewn60cg6.png"
        ),
    )

    embed.timestamp = discord.utils.utcnow()

    return embed


# =========================================================
# REFRESH FLAG MESSAGE
# =========================================================

async def refresh_flag_embed(
    bot: discord.Client,
    guild_id: str,
    map_key: str,
    server: str,
):

    map_key = normalize_map(map_key)
    server = normalize_server(server)

    # =====================================================
    # FIND GUILD FIRST
    # =====================================================

    guild = bot.get_guild(
        int(guild_id)
    )

    if not guild:
        return

    # =====================================================
    # BUILD EMBED WITH GUILD
    # =====================================================

    embed = await create_flag_embed(
        guild_id,
        map_key,
        server,
        guild,
    )

    # =====================================================
    # FIND STORED MESSAGE
    # =====================================================

    async with safe_acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT channel_id, message_id
            FROM flag_messages

            WHERE guild_id = $1
              AND map = $2
              AND server = $3
            """,
            str(guild_id),
            map_key,
            server,
        )

    if not row:
        return

    channel = guild.get_channel(
        int(row["channel_id"])
    )

    if not channel:
        return

    # =====================================================
    # UPDATE MESSAGE
    # =====================================================

    try:

        message = await channel.fetch_message(
            int(row["message_id"])
        )

        await message.edit(
            embed=embed
        )

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException,
    ):
        return
