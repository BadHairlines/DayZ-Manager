from __future__ import annotations

import contextlib
import os
from typing import AsyncIterator, Optional

import asyncpg


db_pool: Optional[asyncpg.Pool] = None


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

    # =====================================================
    # TASKS
    # =====================================================

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS todo_tasks (
            id BIGSERIAL PRIMARY KEY,

            guild_id TEXT NOT NULL,

            title TEXT NOT NULL,
            description TEXT,

            created_by TEXT NOT NULL,
            assigned_to TEXT,

            priority TEXT NOT NULL DEFAULT 'medium',

            status TEXT NOT NULL DEFAULT 'open',

            due_at TIMESTAMPTZ,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            completed_by TEXT
        );
    """)

    # =====================================================
    # BOARD MESSAGE
    # =====================================================

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS todo_boards (
            guild_id TEXT PRIMARY KEY,

            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # =====================================================
    # INDEXES
    # =====================================================

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_guild
        ON todo_tasks (guild_id)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_status
        ON todo_tasks (guild_id, status)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_priority
        ON todo_tasks (guild_id, priority)
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


# =========================================================
# TASK OPERATIONS
# =========================================================

async def create_task(
    guild_id: str,
    title: str,
    description: str | None,
    created_by: str,
    assigned_to: str | None,
    priority: str,
    due_at,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            INSERT INTO todo_tasks (
                guild_id,
                title,
                description,
                created_by,
                assigned_to,
                priority,
                due_at
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7
            )
            RETURNING *
        """,
            str(guild_id),
            title,
            description,
            str(created_by),
            str(assigned_to) if assigned_to else None,
            priority,
            due_at,
        )


async def get_task(
    guild_id: str,
    task_id: int,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            SELECT *
            FROM todo_tasks
            WHERE guild_id=$1
              AND id=$2
        """,
            str(guild_id),
            task_id,
        )


async def get_open_tasks(
    guild_id: str,
):

    async with safe_acquire() as conn:

        return await conn.fetch("""
            SELECT *
            FROM todo_tasks
            WHERE guild_id=$1
              AND status='open'
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END,
                due_at NULLS LAST,
                created_at ASC
        """,
            str(guild_id),
        )


async def get_completed_tasks(
    guild_id: str,
    limit: int = 25,
):

    async with safe_acquire() as conn:

        return await conn.fetch("""
            SELECT *
            FROM todo_tasks
            WHERE guild_id=$1
              AND status='completed'
            ORDER BY completed_at DESC
            LIMIT $2
        """,
            str(guild_id),
            limit,
        )


async def complete_task(
    guild_id: str,
    task_id: int,
    completed_by: str,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            UPDATE todo_tasks
            SET
                status='completed',
                completed_at=NOW(),
                completed_by=$3
            WHERE guild_id=$1
              AND id=$2
              AND status='open'
            RETURNING *
        """,
            str(guild_id),
            task_id,
            str(completed_by),
        )


async def update_task(
    guild_id: str,
    task_id: int,
    title: str,
    description: str | None,
    assigned_to: str | None,
    priority: str,
    due_at,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            UPDATE todo_tasks
            SET
                title=$3,
                description=$4,
                assigned_to=$5,
                priority=$6,
                due_at=$7
            WHERE guild_id=$1
              AND id=$2
              AND status='open'
            RETURNING *
        """,
            str(guild_id),
            task_id,
            title,
            description,
            str(assigned_to) if assigned_to else None,
            priority,
            due_at,
        )


async def delete_task(
    guild_id: str,
    task_id: int,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            DELETE FROM todo_tasks
            WHERE guild_id=$1
              AND id=$2
            RETURNING *
        """,
            str(guild_id),
            task_id,
        )


# =========================================================
# STATISTICS
# =========================================================

async def get_task_stats(
    guild_id: str,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (
                    WHERE status='open'
                ) AS open_count,

                COUNT(*) FILTER (
                    WHERE status='completed'
                ) AS completed_count,

                COUNT(*) AS total_count,

                COUNT(*) FILTER (
                    WHERE status='open'
                    AND priority='critical'
                ) AS critical_count,

                COUNT(*) FILTER (
                    WHERE status='open'
                    AND priority='high'
                ) AS high_count,

                COUNT(*) FILTER (
                    WHERE status='open'
                    AND priority='medium'
                ) AS medium_count,

                COUNT(*) FILTER (
                    WHERE status='open'
                    AND priority='low'
                ) AS low_count

            FROM todo_tasks
            WHERE guild_id=$1
        """,
            str(guild_id),
        )


# =========================================================
# BOARD STORAGE
# =========================================================

async def save_board(
    guild_id: str,
    channel_id: str,
    message_id: str,
) -> None:

    async with safe_acquire() as conn:

        await conn.execute("""
            INSERT INTO todo_boards (
                guild_id,
                channel_id,
                message_id
            )
            VALUES ($1, $2, $3)

            ON CONFLICT (guild_id)

            DO UPDATE SET
                channel_id=EXCLUDED.channel_id,
                message_id=EXCLUDED.message_id
        """,
            str(guild_id),
            str(channel_id),
            str(message_id),
        )


async def get_board(
    guild_id: str,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            SELECT
                channel_id,
                message_id
            FROM todo_boards
            WHERE guild_id=$1
        """,
            str(guild_id),
        )
