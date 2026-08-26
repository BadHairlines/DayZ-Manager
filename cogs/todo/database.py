from __future__ import annotations

import contextlib
import os
from typing import AsyncIterator, Optional

import asyncpg


# =========================================================
# DATABASE
# =========================================================

db_pool: Optional[asyncpg.Pool] = None


# =========================================================
# CONSTANTS
# =========================================================

VALID_PRIORITIES = (
    "critical",
    "high",
    "medium",
    "low",
)

VALID_STATUSES = (
    "open",
    "completed",
    "deleted",
)


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
            os.getenv(
                "TODO_DB_MAX_POOL_SIZE",
                os.getenv(
                    "DB_MAX_POOL_SIZE",
                    "10",
                ),
            )
        ),
        command_timeout=30,
        max_inactive_connection_lifetime=300,
    )

    async with db_pool.acquire() as conn:
        await migrate(conn)

    return db_pool


# =========================================================
# MIGRATION
# =========================================================

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
            completed_by TEXT,

            deleted_at TIMESTAMPTZ,
            deleted_by TEXT
        );
    """)

    # =====================================================
    # BOARD
    # =====================================================

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS todo_boards (
            guild_id TEXT PRIMARY KEY,

            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # =====================================================
    # MIGRATE EXISTING DATABASES
    # =====================================================

    task_columns = {
        row["column_name"]
        for row in await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'todo_tasks'
        """)
    }

    if "deleted_at" not in task_columns:

        await conn.execute("""
            ALTER TABLE todo_tasks
            ADD COLUMN deleted_at TIMESTAMPTZ
        """)

    if "deleted_by" not in task_columns:

        await conn.execute("""
            ALTER TABLE todo_tasks
            ADD COLUMN deleted_by TEXT
        """)

    board_columns = {
        row["column_name"]
        for row in await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'todo_boards'
        """)
    }

    if "updated_at" not in board_columns:

        await conn.execute("""
            ALTER TABLE todo_boards
            ADD COLUMN updated_at TIMESTAMPTZ NOT NULL
            DEFAULT NOW()
        """)

    # =====================================================
    # INDEXES
    # =====================================================

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_guild
        ON todo_tasks (guild_id)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_open
        ON todo_tasks (guild_id, status)
        WHERE status='open'
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_priority
        ON todo_tasks (
            guild_id,
            status,
            priority
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_due
        ON todo_tasks (
            guild_id,
            due_at
        )
        WHERE status='open'
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_todo_tasks_assigned
        ON todo_tasks (
            guild_id,
            assigned_to
        )
    """)


# =========================================================
# SAFE CONNECTION
# =========================================================

@contextlib.asynccontextmanager
async def safe_acquire()
    -> AsyncIterator[asyncpg.Connection]:

    pool = await ensure_connection()

    async with pool.acquire() as conn:
        yield conn


# =========================================================
# SHUTDOWN
# =========================================================

async def close_db() -> None:

    global db_pool

    if db_pool is not None:

        await db_pool.close()

        db_pool = None


# =========================================================
# CREATE TASK
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

    priority = priority.lower().strip()

    if priority not in VALID_PRIORITIES:
        priority = "medium"

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
            title.strip(),
            description,
            str(created_by),
            str(assigned_to)
            if assigned_to
            else None,
            priority,
            due_at,
        )


# =========================================================
# GET TASK
# =========================================================

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


# =========================================================
# OPEN TASKS
# =========================================================

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

                CASE
                    WHEN due_at IS NOT NULL
                     AND due_at < NOW()
                    THEN 0

                    WHEN due_at IS NOT NULL
                    THEN 1

                    ELSE 2
                END,

                due_at NULLS LAST,
                created_at ASC
        """,
            str(guild_id),
        )


# =========================================================
# COMPLETED TASKS
# =========================================================

async def get_completed_tasks(
    guild_id: str,
    limit: int = 50,
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
            max(1, min(limit, 100)),
        )


# =========================================================
# TASK HISTORY
# =========================================================

async def get_task_history(
    guild_id: str,
    limit: int = 100,
):

    async with safe_acquire() as conn:

        return await conn.fetch("""
            SELECT *
            FROM todo_tasks
            WHERE guild_id=$1
              AND status IN (
                  'completed',
                  'deleted'
              )

            ORDER BY
                COALESCE(
                    completed_at,
                    deleted_at,
                    created_at
                ) DESC

            LIMIT $2
        """,
            str(guild_id),
            max(1, min(limit, 100)),
        )


# =========================================================
# COMPLETE TASK
# =========================================================

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


# =========================================================
# DELETE TASK
# =========================================================

async def delete_task(
    guild_id: str,
    task_id: int,
    deleted_by: str,
):

    async with safe_acquire() as conn:

        return await conn.fetchrow("""
            UPDATE todo_tasks
            SET
                status='deleted',
                deleted_at=NOW(),
                deleted_by=$3
            WHERE guild_id=$1
              AND id=$2
              AND status='open'

            RETURNING *
        """,
            str(guild_id),
            task_id,
            str(deleted_by),
        )


# =========================================================
# UPDATE TASK
# =========================================================

async def update_task(
    guild_id: str,
    task_id: int,
    title: str,
    description: str | None,
    assigned_to: str | None,
    priority: str,
    due_at,
):

    priority = priority.lower().strip()

    if priority not in VALID_PRIORITIES:
        priority = "medium"

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
            title.strip(),
            description,
            str(assigned_to)
            if assigned_to
            else None,
            priority,
            due_at,
        )


# =========================================================
# TASK STATISTICS
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

                COUNT(*) FILTER (
                    WHERE status='deleted'
                ) AS deleted_count,

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
                ) AS low_count,

                COUNT(*) FILTER (
                    WHERE status='open'
                    AND due_at IS NOT NULL
                    AND due_at < NOW()
                ) AS overdue_count

            FROM todo_tasks
            WHERE guild_id=$1
        """,
            str(guild_id),
        )


# =========================================================
# BOARD
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
                message_id,
                updated_at
            )
            VALUES (
                $1,
                $2,
                $3,
                NOW()
            )

            ON CONFLICT (guild_id)

            DO UPDATE SET
                channel_id=EXCLUDED.channel_id,
                message_id=EXCLUDED.message_id,
                updated_at=NOW()
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
                guild_id,
                channel_id,
                message_id,
                created_at,
                updated_at
            FROM todo_boards
            WHERE guild_id=$1
        """,
            str(guild_id),
        )


async def delete_board(
    guild_id: str,
) -> bool:

    async with safe_acquire() as conn:

        result = await conn.execute("""
            DELETE FROM todo_boards
            WHERE guild_id=$1
        """,
            str(guild_id),
        )

        return result != "DELETE 0"
