from __future__ import annotations

import contextlib
import json
import os
from typing import Any, AsyncIterator, Optional

import asyncpg
import discord


db_pool: Optional[asyncpg.Pool] = None


# =========================================================
# FLAGS
# =========================================================

FLAGS: list[str] = [
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

FLAG_LOOKUP = {
    flag.casefold(): flag
    for flag in FLAGS
}


CLAIM_SYSTEMS: dict[str, dict[str, Any]] = {
    "flags": {
        "name": "Flags",
        "singular": "Flag",
        "emoji": "🚩",
        "items": FLAGS,
    },
    "raincoats": {
        "name": "Raincoats",
        "singular": "Raincoat",
        "emoji": "🧥",
        "items": [
            "Orange", "Black", "Blue", "Green", "Pink", "Red", "Yellow",
        ],
    },
    "armbands": {
        "name": "Armbands",
        "singular": "Armband",
        "emoji": "🎽",
        "items": [
            "Yellow", "Blue", "Pink", "White", "Green", "Red", "Black", "Orange",
        ],
    },
}

CLAIM_SYSTEM_IMAGES: dict[str, dict[str, str]] = {
    "raincoats": {
        "Orange": "https://i.postimg.cc/Y0p9k0VT/Raincoat-Orange.png",
        "Black": "https://i.postimg.cc/WzX44jck/Raincoat-Black.png",
        "Blue": "https://i.postimg.cc/cCXJJZGX/Raincoat-Blue.png",
        "Green": "https://i.postimg.cc/VsRvg90z/Raincoat-Green.png",
        "Pink": "https://i.postimg.cc/h4rvs8Qf/Raincoat-Pink.png",
        "Red": "https://i.postimg.cc/vHZBN15g/Raincoat-Red.png",
        "Yellow": "https://i.postimg.cc/zGLfq9ty/Raincoat-Yellow.png",
    },
    "armbands": {
        "Yellow": "https://i.postimg.cc/J0gQvfYt/Armband-Yellow.png",
        "Blue": "https://i.postimg.cc/YCQxDy6L/Armband-Blue.png",
        "Pink": "https://i.postimg.cc/fbZfGjCj/Armband-Pink.png",
        "White": "https://i.postimg.cc/QMsJ2kmY/Armband-White.png",
        "Green": "https://i.postimg.cc/cJZBpMTd/Armband-Green.png",
        "Red": "https://i.postimg.cc/1zHrsnY9/Armband-Red.png",
        "Black": "https://i.postimg.cc/vBZLBYp1/Armband-Black.png",
        "Orange": "https://i.postimg.cc/nLHqRVVW/Armband-Orange.png",
    },
}

def normalize_system_type(value: str) -> str:
    value = str(value or "").strip().casefold()
    aliases = {
        "flag": "flags", "flags": "flags",
        "raincoat": "raincoats", "raincoats": "raincoats",
        "armband": "armbands", "armbands": "armbands",
    }
    return aliases.get(value, value)

def system_items(system_type: str) -> list[str]:
    info = CLAIM_SYSTEMS.get(normalize_system_type(system_type))
    return list(info["items"]) if info else []

def normalize_system_item(system_type: str, value: str) -> Optional[str]:
    value_cf = str(value or "").strip().casefold()
    for item in system_items(system_type):
        if item.casefold() == value_cf:
            return item
    return None

def system_channel_name_for(system_type: str, server: str) -> str:
    system_type = normalize_system_type(system_type)
    prefix = {
        "flags": "flags",
        "raincoats": "raincoats",
        "armbands": "armbands",
    }.get(system_type, system_type or "claims")
    server_name = normalize_server(server)
    raw = f"{prefix}-{server_name}"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-")[:100] or prefix


# =========================================================
# MAP DATA
# =========================================================

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
    "nasdara": {
        "name": "Nasdara",
        "image": None,
    },
}


# =========================================================
# EMBED CONFIG
# =========================================================

FOOTER_ICON = "https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"

EMBED_COLOR = 0x3498DB

CLAIMED_EMOJI = "🟥"
AVAILABLE_EMOJI = "🟩"


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_map(value: str) -> str:
    value = str(value or "").strip().casefold()

    aliases = {
        "livonia": "livonia",
        "chernarus": "chernarus",
        "chernarusplus": "chernarus",
        "chernarus plus": "chernarus",
        "sakhal": "sakhal",
        "nasdara": "nasdara",
    }

    return aliases.get(value, value)


def normalize_flag(value: str) -> Optional[str]:
    if not value:
        return None

    return FLAG_LOOKUP.get(
        str(value).strip().casefold()
    )


def normalize_server(value: str) -> str:
    return " ".join(
        str(value or "").strip().casefold().split()
    )


def server_name_includes_map(
    map_key: str,
    server: str,
) -> bool:
    """Return True when the normalized server name already contains its map name."""
    map_key = normalize_map(map_key)
    server_name = normalize_server(server)

    # Current supported map names are single words, so token matching avoids
    # false positives such as a map name merely appearing inside another word.
    tokens = {
        token
        for token in "".join(
            ch if ch.isalnum() else " "
            for ch in server_name
        ).split()
        if token
    }

    return map_key in tokens


def channel_name_for(
    map_key: str,
    server: str,
) -> str:
    """Build Discord flag channel names from the server name only."""
    server_name = normalize_server(server)

    raw = f"flags-{server_name}"

    safe = "".join(
        ch if ch.isalnum() or ch in "-_"
        else "-"
        for ch in raw
    )

    while "--" in safe:
        safe = safe.replace("--", "-")

    return safe.strip("-")[:100] or "flags"


def category_name_for(
    map_key: str,
    server: str,
) -> str:
    """Build a readable setup category without duplicating the map name."""
    map_key = normalize_map(map_key)
    server_name = normalize_server(server)
    map_name = MAP_DATA.get(map_key, {}).get("name", map_key.title())

    if server_name_includes_map(map_key, server_name):
        return f"🌍 {server_name}"

    return f"🌍 {map_name} — {server_name}"


# =========================================================
# DATABASE CONNECTION
# =========================================================

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
        raise RuntimeError(
            "DATABASE_URL environment variable is missing."
        )

    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]

    db_pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=int(
            os.getenv("DB_MAX_POOL_SIZE", "10")
        ),
        command_timeout=30,
        max_inactive_connection_lifetime=300,
    )

    async with db_pool.acquire() as conn:
        await migrate(conn)

    return db_pool


async def migrate(
    conn: asyncpg.Connection,
) -> None:

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
            WHERE table_schema = 'public'
              AND table_name = 'flags'
        """)
    }

    if "server" not in flag_columns:

        await conn.execute("""
            ALTER TABLE flags
            ADD COLUMN server TEXT
            NOT NULL DEFAULT 'server 1'
        """)

        await conn.execute(
            "ALTER TABLE flags "
            "DROP CONSTRAINT IF EXISTS flags_pkey"
        )

        await conn.execute("""
            ALTER TABLE flags
            ADD PRIMARY KEY (
                guild_id,
                map,
                server,
                flag
            )
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
            WHERE table_schema = 'public'
              AND table_name = 'flag_messages'
        """)
    }

    if "server" not in message_columns:

        await conn.execute("""
            ALTER TABLE flag_messages
            ADD COLUMN server TEXT
            NOT NULL DEFAULT 'server 1'
        """)

        await conn.execute(
            "ALTER TABLE flag_messages "
            "DROP CONSTRAINT IF EXISTS flag_messages_pkey"
        )

        await conn.execute("""
            ALTER TABLE flag_messages
            ADD PRIMARY KEY (
                guild_id,
                map,
                server
            )
        """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_flags_lookup
        ON flags (guild_id, map, server)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_flag_messages_guild
        ON flag_messages (guild_id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS flag_audit_log (
            id BIGSERIAL PRIMARY KEY,
            guild_id TEXT NOT NULL,
            map TEXT NOT NULL,
            server TEXT NOT NULL,
            flag TEXT NOT NULL,
            action TEXT NOT NULL,
            role_id TEXT,
            actor_id TEXT,
            source TEXT NOT NULL DEFAULT 'unknown',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_flag_audit_lookup
        ON flag_audit_log (guild_id, map, server, created_at DESC)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS web_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            avatar_url TEXT,
            guild_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            csrf_token TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_sessions_expires
        ON web_sessions (expires_at)
    """)


    await conn.execute("""
        CREATE TABLE IF NOT EXISTS claim_system_items (
            guild_id TEXT NOT NULL,
            map TEXT NOT NULL,
            server TEXT NOT NULL,
            system_type TEXT NOT NULL,
            item TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '✅',
            role_id TEXT,
            PRIMARY KEY (guild_id, map, server, system_type, item)
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_claim_system_items_lookup
        ON claim_system_items (guild_id, map, server, system_type)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS claim_system_messages (
            guild_id TEXT NOT NULL,
            map TEXT NOT NULL,
            server TEXT NOT NULL,
            system_type TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            PRIMARY KEY (guild_id, map, server, system_type)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS claim_system_audit (
            id BIGSERIAL PRIMARY KEY,
            guild_id TEXT NOT NULL,
            map TEXT NOT NULL,
            server TEXT NOT NULL,
            system_type TEXT NOT NULL,
            item TEXT NOT NULL,
            action TEXT NOT NULL,
            role_id TEXT,
            actor_id TEXT,
            source TEXT NOT NULL DEFAULT 'unknown',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_claim_system_audit_lookup
        ON claim_system_audit (guild_id, map, server, system_type, created_at DESC)
    """)


    # =====================================================
    # WEBSITE TASK MANAGER
    # =====================================================

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS server_tasks (
            id BIGSERIAL PRIMARY KEY,
            guild_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'normal',
            status TEXT NOT NULL DEFAULT 'todo',
            category TEXT NOT NULL DEFAULT 'other',
            map TEXT,
            assignee_type TEXT,
            assignee_id TEXT,
            assignee_name TEXT,
            created_by TEXT NOT NULL,
            created_by_name TEXT NOT NULL DEFAULT 'Unknown',
            due_at TIMESTAMPTZ,
            recurrence TEXT NOT NULL DEFAULT 'none',
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_server_tasks_guild_status
        ON server_tasks (guild_id, status, created_at DESC)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_server_tasks_due
        ON server_tasks (guild_id, due_at)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS task_checklist_items (
            id BIGSERIAL PRIMARY KEY,
            task_id BIGINT NOT NULL REFERENCES server_tasks(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            is_done BOOLEAN NOT NULL DEFAULT FALSE,
            position INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_checklist_task
        ON task_checklist_items (task_id, position, id)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS task_comments (
            id BIGSERIAL PRIMARY KEY,
            task_id BIGINT NOT NULL REFERENCES server_tasks(id) ON DELETE CASCADE,
            author_id TEXT NOT NULL,
            author_name TEXT NOT NULL DEFAULT 'Unknown',
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_comments_task
        ON task_comments (task_id, created_at)
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS task_activity (
            id BIGSERIAL PRIMARY KEY,
            task_id BIGINT REFERENCES server_tasks(id) ON DELETE CASCADE,
            guild_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_name TEXT NOT NULL DEFAULT 'Unknown',
            action TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_activity_lookup
        ON task_activity (guild_id, task_id, created_at DESC)
    """)


@contextlib.asynccontextmanager
async def safe_acquire() -> AsyncIterator[asyncpg.Connection]:

    pool = await ensure_connection()

    async with pool.acquire() as conn:
        yield conn


async def database_ready() -> bool:
    try:
        async with safe_acquire() as conn:
            return bool(await conn.fetchval("SELECT 1"))
    except Exception:
        return False


async def save_web_session(session_id: str, user_id: str, username: str,
                           avatar_url: str | None, guild_ids: list[str],
                           csrf_token: str, ttl_seconds: int) -> None:
    async with safe_acquire() as conn:
        await conn.execute("""
            INSERT INTO web_sessions
                (session_id, user_id, username, avatar_url, guild_ids, csrf_token, expires_at)
            VALUES ($1,$2,$3,$4,$5::jsonb,$6,NOW()+($7*INTERVAL '1 second'))
            ON CONFLICT (session_id) DO UPDATE SET
                user_id=EXCLUDED.user_id, username=EXCLUDED.username,
                avatar_url=EXCLUDED.avatar_url, guild_ids=EXCLUDED.guild_ids,
                csrf_token=EXCLUDED.csrf_token, expires_at=EXCLUDED.expires_at
        """, session_id, user_id, username, avatar_url,
             json.dumps([str(x) for x in guild_ids]), csrf_token, int(ttl_seconds))


async def get_web_session(session_id: str) -> dict | None:
    if not session_id:
        return None
    async with safe_acquire() as conn:
        row = await conn.fetchrow("""
            SELECT session_id,user_id,username,avatar_url,guild_ids,csrf_token,expires_at
            FROM web_sessions WHERE session_id=$1 AND expires_at>NOW()
        """, session_id)
        if not row:
            await conn.execute("DELETE FROM web_sessions WHERE session_id=$1", session_id)
            return None
        raw_guild_ids = row["guild_ids"] or []

        # asyncpg may return JSON/JSONB using its default text codec.
        # Decode it before iterating, otherwise a JSON string such as
        # '["123", "456"]' would be treated character-by-character.
        if isinstance(raw_guild_ids, str):
            try:
                raw_guild_ids = json.loads(raw_guild_ids)
            except json.JSONDecodeError:
                raw_guild_ids = []

        if not isinstance(raw_guild_ids, (list, tuple)):
            raw_guild_ids = []

        guild_ids = [str(value) for value in raw_guild_ids if str(value).strip()]

        user = {
            "id": row["user_id"],
            "username": row["username"],
            "avatar_url": row["avatar_url"],
        }

        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "avatar_url": row["avatar_url"],
            "user": user,
            "guild_ids": guild_ids,
            "csrf_token": row["csrf_token"],
            "expires_at": row["expires_at"].timestamp(),
        }


async def delete_web_session(session_id: str) -> None:
    if session_id:
        async with safe_acquire() as conn:
            await conn.execute("DELETE FROM web_sessions WHERE session_id=$1", session_id)


async def close_db() -> None:
    global db_pool

    if db_pool is not None:
        await db_pool.close()
        db_pool = None


# =========================================================
# FLAG DATABASE OPERATIONS
# =========================================================

async def get_flag(
    guild_id: str,
    map_key: str,
    server: str,
    flag: str,
):
    canonical = normalize_flag(flag)

    if not canonical:
        return None

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            SELECT
                guild_id,
                map,
                server,
                flag,
                status,
                role_id
            FROM flags
            WHERE guild_id=$1
              AND map=$2
              AND server=$3
              AND flag=$4
        """,
            str(guild_id),
            normalize_map(map_key),
            normalize_server(server),
            canonical,
        )


async def get_all_flags(
    guild_id: str,
    map_key: str,
    server: str,
):
    async with safe_acquire() as conn:

        return await conn.fetch("""
            SELECT
                guild_id,
                map,
                server,
                flag,
                status,
                role_id
            FROM flags
            WHERE guild_id=$1
              AND map=$2
              AND server=$3
            ORDER BY flag ASC
        """,
            str(guild_id),
            normalize_map(map_key),
            normalize_server(server),
        )


async def initialize_flags(
    guild_id: str,
    map_key: str,
    server: str,
) -> None:

    async with safe_acquire() as conn:

        await conn.executemany("""
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
                '✅',
                NULL
            )
            ON CONFLICT (
                guild_id,
                map,
                server,
                flag
            )
            DO NOTHING
        """, [
            (
                str(guild_id),
                normalize_map(map_key),
                normalize_server(server),
                flag,
            )
            for flag in FLAGS
        ])


async def claim_flag(
    guild_id: str,
    map_key: str,
    server: str,
    flag: str,
    role_id: str,
    *,
    actor_id: str | None = None,
    source: str = "unknown",
):
    canonical = normalize_flag(flag)
    if not canonical:
        return None

    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                UPDATE flags
                SET status='❌', role_id=$5
                WHERE guild_id=$1
                  AND map=$2
                  AND server=$3
                  AND flag=$4
                  AND status='✅'
                  AND role_id IS NULL
                RETURNING *
            """,
                str(guild_id), normalize_map(map_key), normalize_server(server),
                canonical, str(role_id),
            )

            if row:
                await conn.execute("""
                    INSERT INTO flag_audit_log
                        (guild_id, map, server, flag, action, role_id, actor_id, source)
                    VALUES ($1,$2,$3,$4,'claim',$5,$6,$7)
                """,
                    str(guild_id), normalize_map(map_key), normalize_server(server),
                    canonical, str(role_id), str(actor_id) if actor_id else None, source,
                )
            return row


async def release_flag(
    guild_id: str,
    map_key: str,
    server: str,
    flag: str,
    *,
    actor_id: str | None = None,
    source: str = "unknown",
):
    canonical = normalize_flag(flag)
    if not canonical:
        return None

    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                UPDATE flags
                SET status='✅', role_id=NULL
                WHERE guild_id=$1
                  AND map=$2
                  AND server=$3
                  AND flag=$4
                  AND status='❌'
                  AND role_id IS NOT NULL
                RETURNING *
            """,
                str(guild_id), normalize_map(map_key), normalize_server(server), canonical,
            )

            if row:
                await conn.execute("""
                    INSERT INTO flag_audit_log
                        (guild_id, map, server, flag, action, role_id, actor_id, source)
                    VALUES ($1,$2,$3,$4,'release',$5,$6,$7)
                """,
                    str(guild_id), normalize_map(map_key), normalize_server(server),
                    canonical, row['role_id'], str(actor_id) if actor_id else None, source,
                )
            return row


async def get_flag_history(
    guild_id: str,
    map_key: str,
    server: str,
    limit: int = 10,
):
    limit = max(1, min(int(limit), 25))
    async with safe_acquire() as conn:
        return await conn.fetch("""
            SELECT flag, action, role_id, actor_id, source, created_at
            FROM flag_audit_log
            WHERE guild_id=$1 AND map=$2 AND server=$3
            ORDER BY created_at DESC
            LIMIT $4
        """, str(guild_id), normalize_map(map_key), normalize_server(server), limit)


# =========================================================
# FLAG MESSAGE STORAGE
# =========================================================

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
                guild_id,
                map,
                server,
                channel_id,
                message_id
            )
            VALUES ($1, $2, $3, $4, $5)

            ON CONFLICT (
                guild_id,
                map,
                server
            )

            DO UPDATE SET
                channel_id=EXCLUDED.channel_id,
                message_id=EXCLUDED.message_id
        """,
            str(guild_id),
            normalize_map(map_key),
            normalize_server(server),
            str(channel_id),
            str(message_id),
        )


async def get_flag_message(
    guild_id: str,
    map_key: str,
    server: str,
):
    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            SELECT
                channel_id,
                message_id
            FROM flag_messages
            WHERE guild_id=$1
              AND map=$2
              AND server=$3
        """,
            str(guild_id),
            normalize_map(map_key),
            normalize_server(server),
        )


async def get_flag_sessions(
    guild_id: str,
):
    async with safe_acquire() as conn:

        return await conn.fetch("""
            SELECT
                map,
                server,
                channel_id,
                message_id
            FROM flag_messages
            WHERE guild_id=$1
            ORDER BY map, server
        """,
            str(guild_id),
        )


async def get_guild_flag_setups(
    guild_id: str,
):
    """Return every known Flag System name for a guild.

    Unlike get_flag_sessions(), this does not depend on a stored Discord
    dashboard message existing. A setup remains discoverable from its flags
    even if its channel/message record was deleted or became stale.
    """
    async with safe_acquire() as conn:
        return await conn.fetch("""
            SELECT map, server
            FROM (
                SELECT DISTINCT map, server
                FROM flags
                WHERE guild_id=$1

                UNION

                SELECT DISTINCT map, server
                FROM flag_messages
                WHERE guild_id=$1
            ) AS setups
            ORDER BY map, server
        """,
            str(guild_id),
        )


async def get_public_flag_sessions():
    """Return one public summary row per active guild/map/server Flag System."""
    async with safe_acquire() as conn:
        return await conn.fetch("""
            SELECT
                guild_id,
                map,
                server,
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE role_id IS NULL AND status = '✅'
                ) AS available_count,
                COUNT(*) FILTER (
                    WHERE role_id IS NOT NULL OR status = '❌'
                ) AS claimed_count
            FROM flags
            GROUP BY guild_id, map, server
            ORDER BY guild_id, map, server
        """)


async def flag_session_exists(
    guild_id: str,
    map_key: str,
    server: str,
) -> bool:
    async with safe_acquire() as conn:
        value = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1
                FROM flags
                WHERE guild_id=$1
                  AND map=$2
                  AND server=$3
            ) OR EXISTS (
                SELECT 1
                FROM flag_messages
                WHERE guild_id=$1
                  AND map=$2
                  AND server=$3
            )
        """,
            str(guild_id),
            normalize_map(map_key),
            normalize_server(server),
        )
        return bool(value)


async def rename_flag_session(
    guild_id: str,
    map_key: str,
    old_server: str,
    new_server: str,
) -> dict[str, int]:
    """Atomically rename one guild/map Flag System across all database tables."""
    guild_id = str(guild_id)
    map_key = normalize_map(map_key)
    old_server = normalize_server(old_server)
    new_server = normalize_server(new_server)

    if not old_server or not new_server:
        raise ValueError("Both the current and new setup names are required.")
    if old_server == new_server:
        raise ValueError("The new setup name is the same as the current name.")

    async with safe_acquire() as conn:
        async with conn.transaction():
            source_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM flags
                    WHERE guild_id=$1 AND map=$2 AND server=$3
                ) OR EXISTS (
                    SELECT 1 FROM flag_messages
                    WHERE guild_id=$1 AND map=$2 AND server=$3
                )
            """, guild_id, map_key, old_server)
            if not source_exists:
                raise LookupError("The Flag System you are trying to rename no longer exists.")

            destination_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM flags
                    WHERE guild_id=$1 AND map=$2 AND server=$3
                ) OR EXISTS (
                    SELECT 1 FROM flag_messages
                    WHERE guild_id=$1 AND map=$2 AND server=$3
                )
            """, guild_id, map_key, new_server)
            if destination_exists:
                raise FileExistsError("A Flag System with that name already exists for this map.")

            flags_result = await conn.execute("""
                UPDATE flags SET server=$4
                WHERE guild_id=$1 AND map=$2 AND server=$3
            """, guild_id, map_key, old_server, new_server)
            messages_result = await conn.execute("""
                UPDATE flag_messages SET server=$4
                WHERE guild_id=$1 AND map=$2 AND server=$3
            """, guild_id, map_key, old_server, new_server)
            audit_result = await conn.execute("""
                UPDATE flag_audit_log SET server=$4
                WHERE guild_id=$1 AND map=$2 AND server=$3
            """, guild_id, map_key, old_server, new_server)

    def _count(result: str) -> int:
        try:
            return int(result.rsplit(" ", 1)[-1])
        except (TypeError, ValueError):
            return 0

    return {
        "flags": _count(flags_result),
        "messages": _count(messages_result),
        "audit": _count(audit_result),
    }


async def delete_flag_session(
    guild_id: str,
    map_key: str,
    server: str,
) -> dict[str, int]:
    """Permanently delete one guild-scoped flag setup from the database."""
    guild_id = str(guild_id)
    map_key = normalize_map(map_key)
    server = normalize_server(server)

    async with safe_acquire() as conn:
        async with conn.transaction():
            flags_result = await conn.execute("""
                DELETE FROM flags
                WHERE guild_id=$1
                  AND map=$2
                  AND server=$3
            """, guild_id, map_key, server)

            messages_result = await conn.execute("""
                DELETE FROM flag_messages
                WHERE guild_id=$1
                  AND map=$2
                  AND server=$3
            """, guild_id, map_key, server)

            audit_result = await conn.execute("""
                DELETE FROM flag_audit_log
                WHERE guild_id=$1
                  AND map=$2
                  AND server=$3
            """, guild_id, map_key, server)

    def _count(command_result: str) -> int:
        try:
            return int(command_result.rsplit(" ", 1)[-1])
        except (TypeError, ValueError):
            return 0

    return {
        "flags": _count(flags_result),
        "messages": _count(messages_result),
        "audit": _count(audit_result),
    }


# =========================================================
# FLAG EMOJIS
# =========================================================

def flag_emoji(
    guild: discord.Guild | None,
    flag: str,
    claimed: bool,
) -> str:

    if guild:
        custom = discord.utils.get(
            guild.emojis,
            name=flag,
        )

        if custom:
            return f"{custom} "

    return (
        f"{CLAIMED_EMOJI} "
        if claimed
        else f"{AVAILABLE_EMOJI} "
    )


# =========================================================
# EMBED HELPERS
# =========================================================

def _split_embed_lines(
    lines: list[str],
    max_length: int = 1024,
) -> list[str]:

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for line in lines:

        line_length = len(line)

        extra_length = (
            line_length
            if not current
            else line_length + 1
        )

        if (
            current
            and current_length + extra_length > max_length
        ):
            chunks.append(
                "\n".join(current)
            )

            current = [line]
            current_length = line_length

        else:
            current.append(line)
            current_length += extra_length

    if current:
        chunks.append(
            "\n".join(current)
        )

    return chunks


def _ownership_bar(
    claimed: int,
    total: int,
    length: int = 12,
) -> str:

    if total <= 0:
        return "⬜" * length

    ratio = claimed / total

    filled = round(
        ratio * length
    )

    filled = max(
        0,
        min(length, filled),
    )

    return (
        "🟥" * filled
        + "⬜" * (length - filled)
    )


# =========================================================
# FLAG EMBED
# =========================================================

async def create_flag_embed(
    guild_id: str,
    map_key: str,
    server: str,
    guild: discord.Guild | None = None,
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

    # -----------------------------------------------------
    # SORT FLAGS
    # -----------------------------------------------------

    rows = sorted(
        rows,
        key=lambda row: str(
            row["flag"]
        ).casefold(),
    )

    # -----------------------------------------------------
    # DETERMINE STATUS
    # -----------------------------------------------------

    claimed = [
        row
        for row in rows
        if row["role_id"]
        or row["status"] == "❌"
    ]

    available = [
        row
        for row in rows
        if not (
            row["role_id"]
            or row["status"] == "❌"
        )
    ]

    total = len(rows)
    claimed_count = len(claimed)
    available_count = len(available)

    claimed_percent = (
        (claimed_count / total) * 100
        if total
        else 0
    )

    # =====================================================
    # MAIN EMBED
    # =====================================================

    embed = discord.Embed(
        title="🏴  FLAG OWNERSHIP",
        description=(
            f"**{map_info['name']}**  •  `{server}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{CLAIMED_EMOJI} **{claimed_count}** Claimed"
            f"   •   "
            f"{AVAILABLE_EMOJI} **{available_count}** Available"
            f"   •   "
            f"**{total}** Total\n\n"
            f"{_ownership_bar(claimed_count, total)}  "
            f"**{claimed_percent:.0f}% Claimed**"
        ),
        color=EMBED_COLOR,
    )

    # =====================================================
    # MAP IMAGE
    # =====================================================

    if map_info.get("image"):
        embed.set_image(
            url=map_info["image"]
        )

    # =====================================================
    # NO FLAGS
    # =====================================================

    if not rows:

        embed.add_field(
            name="🏴  FLAG REGISTRY",
            value=(
                "There are currently **no flags configured** "
                "for this server."
            ),
            inline=False,
        )

    # =====================================================
    # CLAIMED FLAGS
    # =====================================================

    if claimed:

        claimed_lines: list[str] = []

        for row in claimed:

            emoji = flag_emoji(
                guild,
                row["flag"],
                claimed=True,
            )

            role_id = row["role_id"]

            owner = (
                f"<@&{role_id}>"
                if role_id
                else "*Assigned*"
            )

            claimed_lines.append(
                f"{emoji}**{row['flag']}**  —  {owner}"
            )

        for chunk in _split_embed_lines(
            claimed_lines
        ):

            embed.add_field(
                name="🟥  CLAIMED FLAGS",
                value=chunk,
                inline=False,
            )

    # =====================================================
    # AVAILABLE FLAGS
    # =====================================================

    if available:

        available_lines: list[str] = []

        for row in available:

            emoji = flag_emoji(
                guild,
                row["flag"],
                claimed=False,
            )

            available_lines.append(
                f"{emoji}**{row['flag']}**  —  "
                "*Available for claiming*"
            )

        for chunk in _split_embed_lines(
            available_lines
        ):

            embed.add_field(
                name="🟩  AVAILABLE FLAGS",
                value=chunk,
                inline=False,
            )

    # =====================================================
    # FOOTER
    # =====================================================

    embed.set_footer(
        text="DayZ Manager  •  Flag Management",
        icon_url=FOOTER_ICON,
    )

    embed.timestamp = discord.utils.utcnow()

    return embed


# =========================================================
# REFRESH FLAG EMBED
# =========================================================

async def refresh_flag_embed(
    bot: discord.Client,
    guild_id: str,
    map_key: str,
    server: str,
) -> bool:

    guild = bot.get_guild(
        int(guild_id)
    )

    if not guild:
        return False

    row = await get_flag_message(
        guild_id,
        map_key,
        server,
    )

    if not row:
        return False

    channel = guild.get_channel(
        int(row["channel_id"])
    )

    if not isinstance(
        channel,
        discord.TextChannel,
    ):
        return False

    try:

        message = await channel.fetch_message(
            int(row["message_id"])
        )

        embed = await create_flag_embed(
            guild_id,
            map_key,
            server,
            guild,
        )

        await message.edit(
            embed=embed
        )

        return True

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException,
    ):
        return False




# =========================================================
# NON-FLAG CLAIM SYSTEMS (RAINCOATS / ARMBANDS)
# =========================================================

async def initialize_claim_system(
    guild_id: str,
    map_key: str,
    server: str,
    system_type: str,
) -> None:
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        await initialize_flags(guild_id, map_key, server)
        return
    items = system_items(system_type)
    if not items:
        raise ValueError("Invalid claim system type.")
    async with safe_acquire() as conn:
        await conn.executemany("""
            INSERT INTO claim_system_items
                (guild_id,map,server,system_type,item,status,role_id)
            VALUES ($1,$2,$3,$4,$5,'✅',NULL)
            ON CONFLICT (guild_id,map,server,system_type,item) DO NOTHING
        """, [
            (str(guild_id), normalize_map(map_key), normalize_server(server), system_type, item)
            for item in items
        ])


async def get_claim_system_items(
    guild_id: str,
    map_key: str,
    server: str,
    system_type: str,
):
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        return await get_all_flags(guild_id, map_key, server)
    async with safe_acquire() as conn:
        return await conn.fetch("""
            SELECT item AS flag,status,role_id
            FROM claim_system_items
            WHERE guild_id=$1 AND map=$2 AND server=$3 AND system_type=$4
            ORDER BY LOWER(item)
        """, str(guild_id), normalize_map(map_key), normalize_server(server), system_type)


async def claim_system_item(
    guild_id: str,
    map_key: str,
    server: str,
    system_type: str,
    item: str,
    role_id: str,
    actor_id: str | None = None,
    source: str = "unknown",
) -> bool:
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        return await claim_flag(
            guild_id,map_key,server,item,role_id,actor_id=actor_id,source=source
        )
    item = normalize_system_item(system_type, item)
    if not item:
        return False
    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                UPDATE claim_system_items
                SET status='❌', role_id=$6
                WHERE guild_id=$1 AND map=$2 AND server=$3
                  AND system_type=$4 AND item=$5
                  AND status='✅' AND role_id IS NULL
                RETURNING item
            """, str(guild_id), normalize_map(map_key), normalize_server(server),
                 system_type, item, str(role_id))
            if not row:
                return False
            await conn.execute("""
                INSERT INTO claim_system_audit
                    (guild_id,map,server,system_type,item,action,role_id,actor_id,source)
                VALUES ($1,$2,$3,$4,$5,'claim',$6,$7,$8)
            """, str(guild_id), normalize_map(map_key), normalize_server(server),
                 system_type, item, str(role_id), actor_id, source)
            return True


async def release_system_item(
    guild_id: str,
    map_key: str,
    server: str,
    system_type: str,
    item: str,
    actor_id: str | None = None,
    source: str = "unknown",
) -> bool:
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        return await release_flag(
            guild_id,map_key,server,item,actor_id=actor_id,source=source
        )
    item = normalize_system_item(system_type, item)
    if not item:
        return False
    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT role_id FROM claim_system_items
                WHERE guild_id=$1 AND map=$2 AND server=$3
                  AND system_type=$4 AND item=$5
                FOR UPDATE
            """, str(guild_id), normalize_map(map_key), normalize_server(server),
                 system_type, item)
            if not row or (row["role_id"] is None):
                return False
            old_role = row["role_id"]
            await conn.execute("""
                UPDATE claim_system_items
                SET status='✅', role_id=NULL
                WHERE guild_id=$1 AND map=$2 AND server=$3
                  AND system_type=$4 AND item=$5
            """, str(guild_id), normalize_map(map_key), normalize_server(server),
                 system_type, item)
            await conn.execute("""
                INSERT INTO claim_system_audit
                    (guild_id,map,server,system_type,item,action,role_id,actor_id,source)
                VALUES ($1,$2,$3,$4,$5,'release',$6,$7,$8)
            """, str(guild_id), normalize_map(map_key), normalize_server(server),
                 system_type, item, old_role, actor_id, source)
            return True


async def save_claim_system_message(
    guild_id: str,map_key: str,server: str,system_type: str,
    channel_id: str,message_id: str,
) -> None:
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        await save_flag_message(guild_id,map_key,server,channel_id,message_id)
        return
    async with safe_acquire() as conn:
        await conn.execute("""
            INSERT INTO claim_system_messages
                (guild_id,map,server,system_type,channel_id,message_id)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (guild_id,map,server,system_type)
            DO UPDATE SET channel_id=EXCLUDED.channel_id,message_id=EXCLUDED.message_id
        """, str(guild_id),normalize_map(map_key),normalize_server(server),
             system_type,str(channel_id),str(message_id))


async def get_claim_system_message(
    guild_id: str,map_key: str,server: str,system_type: str,
):
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        return await get_flag_message(guild_id,map_key,server)
    async with safe_acquire() as conn:
        return await conn.fetchrow("""
            SELECT channel_id,message_id
            FROM claim_system_messages
            WHERE guild_id=$1 AND map=$2 AND server=$3 AND system_type=$4
        """, str(guild_id),normalize_map(map_key),normalize_server(server),system_type)


async def get_nonflag_claim_sessions(guild_id: str):
    async with safe_acquire() as conn:
        return await conn.fetch("""
            SELECT map,server,system_type,channel_id,message_id
            FROM claim_system_messages
            WHERE guild_id=$1
            ORDER BY system_type,map,server
        """, str(guild_id))


async def claim_system_exists(
    guild_id: str,map_key: str,server: str,system_type: str,
) -> bool:
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        return await flag_session_exists(guild_id,map_key,server)
    async with safe_acquire() as conn:
        return bool(await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM claim_system_items
                WHERE guild_id=$1 AND map=$2 AND server=$3 AND system_type=$4
            )
        """, str(guild_id),normalize_map(map_key),normalize_server(server),system_type))


async def delete_claim_system(
    guild_id: str,map_key: str,server: str,system_type: str,
) -> dict[str,int]:
    system_type = normalize_system_type(system_type)
    if system_type == "flags":
        return await delete_flag_session(guild_id,map_key,server)
    async with safe_acquire() as conn:
        async with conn.transaction():
            audit = await conn.execute("""
                DELETE FROM claim_system_audit
                WHERE guild_id=$1 AND map=$2 AND server=$3 AND system_type=$4
            """,str(guild_id),normalize_map(map_key),normalize_server(server),system_type)
            msg = await conn.execute("""
                DELETE FROM claim_system_messages
                WHERE guild_id=$1 AND map=$2 AND server=$3 AND system_type=$4
            """,str(guild_id),normalize_map(map_key),normalize_server(server),system_type)
            items = await conn.execute("""
                DELETE FROM claim_system_items
                WHERE guild_id=$1 AND map=$2 AND server=$3 AND system_type=$4
            """,str(guild_id),normalize_map(map_key),normalize_server(server),system_type)
            def count(result: str) -> int:
                try: return int(result.rsplit(" ",1)[-1])
                except Exception: return 0
            return {"flags":count(items),"messages":count(msg),"audit":count(audit)}


# =========================================================
# WEBSITE TASK MANAGER
# =========================================================

TASK_STATUSES = {"todo", "in_progress", "review", "completed"}
TASK_PRIORITIES = {"low", "normal", "high", "urgent"}
TASK_RECURRENCES = {"none", "daily", "weekly", "monthly"}
TASK_CATEGORIES = {
    "server", "custom_base", "trader", "event", "flag_system",
    "xml_config", "bug", "website", "discord", "other",
}


def _task_row(row) -> dict:
    if not row:
        return {}
    return {
        "id": int(row["id"]),
        "guild_id": str(row["guild_id"]),
        "title": str(row["title"]),
        "description": str(row["description"] or ""),
        "priority": str(row["priority"]),
        "status": str(row["status"]),
        "category": str(row["category"]),
        "map": row["map"],
        "assignee_type": row["assignee_type"],
        "assignee_id": row["assignee_id"],
        "assignee_name": row["assignee_name"],
        "created_by": str(row["created_by"]),
        "created_by_name": str(row["created_by_name"] or "Unknown"),
        "due_at": row["due_at"].isoformat() if row["due_at"] else None,
        "recurrence": str(row["recurrence"] or "none"),
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def _task_activity(
    conn: asyncpg.Connection,
    guild_id: str,
    task_id: int | None,
    actor_id: str,
    actor_name: str,
    action: str,
    details: str = "",
) -> None:
    await conn.execute("""
        INSERT INTO task_activity
            (task_id, guild_id, actor_id, actor_name, action, details)
        VALUES ($1,$2,$3,$4,$5,$6)
    """, task_id, str(guild_id), str(actor_id), str(actor_name), action, details[:1500])


async def get_tasks(guild_id: str, include_completed: bool = True) -> list[dict]:
    async with safe_acquire() as conn:
        if include_completed:
            rows = await conn.fetch("""
                SELECT * FROM server_tasks
                WHERE guild_id=$1
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'normal' THEN 3
                        ELSE 4
                    END,
                    due_at NULLS LAST,
                    created_at DESC
            """, str(guild_id))
        else:
            rows = await conn.fetch("""
                SELECT * FROM server_tasks
                WHERE guild_id=$1 AND status <> 'completed'
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'normal' THEN 3
                        ELSE 4
                    END,
                    due_at NULLS LAST,
                    created_at DESC
            """, str(guild_id))
        return [_task_row(row) for row in rows]


async def get_task(guild_id: str, task_id: int) -> dict | None:
    async with safe_acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM server_tasks WHERE guild_id=$1 AND id=$2",
            str(guild_id), int(task_id),
        )
        return _task_row(row) if row else None


async def create_task(
    guild_id: str,
    title: str,
    description: str,
    priority: str,
    status: str,
    category: str,
    map_key: str | None,
    assignee_type: str | None,
    assignee_id: str | None,
    assignee_name: str | None,
    due_at,
    recurrence: str,
    actor_id: str,
    actor_name: str,
) -> dict:
    priority = priority if priority in TASK_PRIORITIES else "normal"
    status = status if status in TASK_STATUSES else "todo"
    category = category if category in TASK_CATEGORIES else "other"
    recurrence = recurrence if recurrence in TASK_RECURRENCES else "none"

    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                INSERT INTO server_tasks (
                    guild_id,title,description,priority,status,category,map,
                    assignee_type,assignee_id,assignee_name,
                    created_by,created_by_name,due_at,recurrence,
                    completed_at
                )
                VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,
                    CASE WHEN $5='completed' THEN NOW() ELSE NULL END
                )
                RETURNING *
            """,
                str(guild_id), title[:160], description[:5000], priority, status,
                category, normalize_map(map_key) if map_key else None,
                assignee_type, assignee_id, assignee_name,
                str(actor_id), actor_name[:120], due_at, recurrence,
            )
            task = _task_row(row)
            await _task_activity(
                conn, guild_id, task["id"], actor_id, actor_name,
                "created", f"Created task: {task['title']}",
            )
            return task


async def update_task(
    guild_id: str,
    task_id: int,
    *,
    title: str,
    description: str,
    priority: str,
    status: str,
    category: str,
    map_key: str | None,
    assignee_type: str | None,
    assignee_id: str | None,
    assignee_name: str | None,
    due_at,
    recurrence: str,
    actor_id: str,
    actor_name: str,
) -> dict | None:
    priority = priority if priority in TASK_PRIORITIES else "normal"
    status = status if status in TASK_STATUSES else "todo"
    category = category if category in TASK_CATEGORIES else "other"
    recurrence = recurrence if recurrence in TASK_RECURRENCES else "none"

    async with safe_acquire() as conn:
        async with conn.transaction():
            previous = await conn.fetchrow(
                "SELECT * FROM server_tasks WHERE guild_id=$1 AND id=$2 FOR UPDATE",
                str(guild_id), int(task_id),
            )
            if not previous:
                return None

            row = await conn.fetchrow("""
                UPDATE server_tasks SET
                    title=$3, description=$4, priority=$5, status=$6,
                    category=$7, map=$8, assignee_type=$9, assignee_id=$10,
                    assignee_name=$11, due_at=$12, recurrence=$13,
                    completed_at=CASE
                        WHEN $6='completed' AND completed_at IS NULL THEN NOW()
                        WHEN $6<>'completed' THEN NULL
                        ELSE completed_at
                    END,
                    updated_at=NOW()
                WHERE guild_id=$1 AND id=$2
                RETURNING *
            """,
                str(guild_id), int(task_id), title[:160], description[:5000],
                priority, status, category,
                normalize_map(map_key) if map_key else None,
                assignee_type, assignee_id, assignee_name,
                due_at, recurrence,
            )
            task = _task_row(row)
            changes = []
            for field in ("title","priority","status","category","map","assignee_name","recurrence"):
                old = previous[field]
                new = row[field]
                if old != new:
                    changes.append(f"{field}: {old or 'none'} → {new or 'none'}")
            await _task_activity(
                conn, guild_id, int(task_id), actor_id, actor_name,
                "updated", "; ".join(changes) or "Task details updated",
            )
            return task


async def set_task_status(
    guild_id: str,
    task_id: int,
    status: str,
    actor_id: str,
    actor_name: str,
) -> dict | None:
    if status not in TASK_STATUSES:
        raise ValueError("Invalid task status.")

    async with safe_acquire() as conn:
        async with conn.transaction():
            previous = await conn.fetchrow(
                "SELECT * FROM server_tasks WHERE guild_id=$1 AND id=$2 FOR UPDATE",
                str(guild_id), int(task_id),
            )
            if not previous:
                return None

            row = await conn.fetchrow("""
                UPDATE server_tasks SET
                    status=$3,
                    completed_at=CASE
                        WHEN $3='completed' THEN COALESCE(completed_at,NOW())
                        ELSE NULL
                    END,
                    updated_at=NOW()
                WHERE guild_id=$1 AND id=$2
                RETURNING *
            """, str(guild_id), int(task_id), status)

            await _task_activity(
                conn, guild_id, int(task_id), actor_id, actor_name,
                "status_changed", f"{previous['status']} → {status}",
            )

            # Recurring tasks produce the next instance on first completion.
            if (
                status == "completed"
                and previous["status"] != "completed"
                and row["recurrence"] in {"daily","weekly","monthly"}
            ):
                if row["due_at"]:
                    if row["recurrence"] == "daily":
                        next_due = row["due_at"] + __import__("datetime").timedelta(days=1)
                    elif row["recurrence"] == "weekly":
                        next_due = row["due_at"] + __import__("datetime").timedelta(days=7)
                    else:
                        dt = row["due_at"]
                        year = dt.year + (1 if dt.month == 12 else 0)
                        month = 1 if dt.month == 12 else dt.month + 1
                        import calendar
                        day = min(dt.day, calendar.monthrange(year, month)[1])
                        next_due = dt.replace(year=year, month=month, day=day)
                else:
                    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                    if row["recurrence"] == "daily":
                        next_due = now + __import__("datetime").timedelta(days=1)
                    elif row["recurrence"] == "weekly":
                        next_due = now + __import__("datetime").timedelta(days=7)
                    else:
                        year = now.year + (1 if now.month == 12 else 0)
                        month = 1 if now.month == 12 else now.month + 1
                        import calendar
                        day = min(now.day, calendar.monthrange(year, month)[1])
                        next_due = now.replace(year=year, month=month, day=day)

                next_row = await conn.fetchrow("""
                    INSERT INTO server_tasks (
                        guild_id,title,description,priority,status,category,map,
                        assignee_type,assignee_id,assignee_name,
                        created_by,created_by_name,due_at,recurrence
                    )
                    VALUES ($1,$2,$3,$4,'todo',$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    RETURNING id
                """,
                    row["guild_id"], row["title"], row["description"], row["priority"],
                    row["category"], row["map"], row["assignee_type"], row["assignee_id"],
                    row["assignee_name"], str(actor_id), actor_name[:120],
                    next_due, row["recurrence"],
                )
                # Carry checklist structure forward as a fresh template.
                await conn.execute("""
                    INSERT INTO task_checklist_items (task_id, text, is_done, position)
                    SELECT $1, text, FALSE, position
                    FROM task_checklist_items
                    WHERE task_id=$2
                    ORDER BY position, id
                """, int(next_row["id"]), int(task_id))

                await _task_activity(
                    conn, guild_id, int(next_row["id"]), actor_id, actor_name,
                    "recurring_created", f"Created from recurring task #{task_id}",
                )

            return _task_row(row)


async def claim_task(
    guild_id: str,
    task_id: int,
    actor_id: str,
    actor_name: str,
) -> dict | None:
    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                UPDATE server_tasks SET
                    assignee_type='user',
                    assignee_id=$3,
                    assignee_name=$4,
                    status=CASE WHEN status='todo' THEN 'in_progress' ELSE status END,
                    updated_at=NOW()
                WHERE guild_id=$1 AND id=$2
                RETURNING *
            """, str(guild_id), int(task_id), str(actor_id), actor_name[:120])
            if not row:
                return None
            await _task_activity(
                conn, guild_id, int(task_id), actor_id, actor_name,
                "claimed", f"Claimed by {actor_name}",
            )
            return _task_row(row)


async def delete_task(
    guild_id: str,
    task_id: int,
    actor_id: str,
    actor_name: str,
) -> bool:
    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT title FROM server_tasks WHERE guild_id=$1 AND id=$2 FOR UPDATE",
                str(guild_id), int(task_id),
            )
            if not row:
                return False
            await _task_activity(
                conn, guild_id, None, actor_id, actor_name,
                "deleted", f"Deleted task #{task_id}: {row['title']}",
            )
            await conn.execute(
                "DELETE FROM server_tasks WHERE guild_id=$1 AND id=$2",
                str(guild_id), int(task_id),
            )
            return True


async def get_task_checklist(guild_id: str, task_id: int) -> list[dict]:
    async with safe_acquire() as conn:
        rows = await conn.fetch("""
            SELECT c.id,c.text,c.is_done,c.position,c.created_at
            FROM task_checklist_items c
            JOIN server_tasks t ON t.id=c.task_id
            WHERE t.guild_id=$1 AND c.task_id=$2
            ORDER BY c.position,c.id
        """, str(guild_id), int(task_id))
        return [
            {
                "id": int(row["id"]), "text": str(row["text"]),
                "is_done": bool(row["is_done"]), "position": int(row["position"]),
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]


async def add_task_checklist_item(
    guild_id: str, task_id: int, text: str,
    actor_id: str, actor_name: str,
) -> dict | None:
    async with safe_acquire() as conn:
        async with conn.transaction():
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM server_tasks WHERE guild_id=$1 AND id=$2)",
                str(guild_id), int(task_id),
            )
            if not exists:
                return None
            position = await conn.fetchval(
                "SELECT COALESCE(MAX(position),-1)+1 FROM task_checklist_items WHERE task_id=$1",
                int(task_id),
            )
            row = await conn.fetchrow("""
                INSERT INTO task_checklist_items (task_id,text,position)
                VALUES ($1,$2,$3)
                RETURNING id,text,is_done,position,created_at
            """, int(task_id), text[:500], int(position))
            await _task_activity(
                conn, guild_id, int(task_id), actor_id, actor_name,
                "checklist_added", text[:500],
            )
            return {
                "id": int(row["id"]), "text": str(row["text"]),
                "is_done": bool(row["is_done"]), "position": int(row["position"]),
                "created_at": row["created_at"].isoformat(),
            }


async def toggle_task_checklist_item(
    guild_id: str, task_id: int, item_id: int,
    actor_id: str, actor_name: str,
) -> dict | None:
    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                UPDATE task_checklist_items c
                SET is_done=NOT c.is_done
                FROM server_tasks t
                WHERE c.id=$1 AND c.task_id=$2 AND t.id=c.task_id AND t.guild_id=$3
                RETURNING c.id,c.text,c.is_done,c.position,c.created_at
            """, int(item_id), int(task_id), str(guild_id))
            if not row:
                return None
            await _task_activity(
                conn, guild_id, int(task_id), actor_id, actor_name,
                "checklist_toggled",
                f"{'Completed' if row['is_done'] else 'Reopened'}: {row['text']}",
            )
            return {
                "id": int(row["id"]), "text": str(row["text"]),
                "is_done": bool(row["is_done"]), "position": int(row["position"]),
                "created_at": row["created_at"].isoformat(),
            }


async def delete_task_checklist_item(
    guild_id: str, task_id: int, item_id: int,
    actor_id: str, actor_name: str,
) -> bool:
    async with safe_acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                SELECT c.text FROM task_checklist_items c
                JOIN server_tasks t ON t.id=c.task_id
                WHERE c.id=$1 AND c.task_id=$2 AND t.guild_id=$3
            """, int(item_id), int(task_id), str(guild_id))
            if not row:
                return False
            await conn.execute("DELETE FROM task_checklist_items WHERE id=$1", int(item_id))
            await _task_activity(
                conn, guild_id, int(task_id), actor_id, actor_name,
                "checklist_deleted", str(row["text"]),
            )
            return True


async def get_task_comments(guild_id: str, task_id: int) -> list[dict]:
    async with safe_acquire() as conn:
        rows = await conn.fetch("""
            SELECT c.id,c.author_id,c.author_name,c.body,c.created_at
            FROM task_comments c
            JOIN server_tasks t ON t.id=c.task_id
            WHERE t.guild_id=$1 AND c.task_id=$2
            ORDER BY c.created_at ASC
        """, str(guild_id), int(task_id))
        return [
            {
                "id": int(row["id"]), "author_id": str(row["author_id"]),
                "author_name": str(row["author_name"]), "body": str(row["body"]),
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]


async def add_task_comment(
    guild_id: str, task_id: int, body: str,
    actor_id: str, actor_name: str,
) -> dict | None:
    async with safe_acquire() as conn:
        async with conn.transaction():
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM server_tasks WHERE guild_id=$1 AND id=$2)",
                str(guild_id), int(task_id),
            )
            if not exists:
                return None
            row = await conn.fetchrow("""
                INSERT INTO task_comments (task_id,author_id,author_name,body)
                VALUES ($1,$2,$3,$4)
                RETURNING id,author_id,author_name,body,created_at
            """, int(task_id), str(actor_id), actor_name[:120], body[:3000])
            await _task_activity(
                conn, guild_id, int(task_id), actor_id, actor_name,
                "commented", body[:500],
            )
            return {
                "id": int(row["id"]), "author_id": str(row["author_id"]),
                "author_name": str(row["author_name"]), "body": str(row["body"]),
                "created_at": row["created_at"].isoformat(),
            }


async def get_task_activity(guild_id: str, task_id: int, limit: int = 50) -> list[dict]:
    async with safe_acquire() as conn:
        rows = await conn.fetch("""
            SELECT id,actor_id,actor_name,action,details,created_at
            FROM task_activity
            WHERE guild_id=$1 AND task_id=$2
            ORDER BY created_at DESC
            LIMIT $3
        """, str(guild_id), int(task_id), max(1, min(int(limit), 100)))
        return [
            {
                "id": int(row["id"]), "actor_id": str(row["actor_id"]),
                "actor_name": str(row["actor_name"]), "action": str(row["action"]),
                "details": str(row["details"] or ""),
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]


async def get_task_summary(guild_id: str) -> dict:
    async with safe_acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status='todo') AS todo,
                COUNT(*) FILTER (WHERE status='in_progress') AS in_progress,
                COUNT(*) FILTER (WHERE status='review') AS review,
                COUNT(*) FILTER (WHERE status='completed') AS completed,
                COUNT(*) FILTER (
                    WHERE status<>'completed' AND due_at IS NOT NULL AND due_at<NOW()
                ) AS overdue
            FROM server_tasks
            WHERE guild_id=$1
        """, str(guild_id))
        return {key: int(row[key] or 0) for key in ("todo","in_progress","review","completed","overdue")}

