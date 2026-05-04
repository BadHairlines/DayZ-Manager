import os
import asyncpg
from typing import Optional

pool: asyncpg.Pool | None = None


FLAGS = [
    "APA","Altis","BabyDeer","Bear","Bohemia","BrainZ","Cannibals",
    "CHEL","Chedaki","CMC","Crook","HunterZ","NAPA","NSahrani",
    "Pirates","Rex","Refuge","Rooster","RSTA","Snake",
    "TEC","UEC","Wolf","Zagorky","Zenit"
]

MAP_DATA = {
    "livonia": {"name": "Livonia", "image": "..."},
    "chernarus": {"name": "Chernarus", "image": "..."},
    "sakhal": {"name": "Sakhal", "image": "..."},
}


async def init_db():
    global pool
    if pool:
        return pool

    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=1, max_size=5)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS flags (
            guild_id TEXT,
            map TEXT,
            flag TEXT,
            status TEXT,
            role_id TEXT,
            PRIMARY KEY (guild_id, map, flag)
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS flag_messages (
            guild_id TEXT,
            map TEXT,
            channel_id TEXT,
            message_id TEXT,
            PRIMARY KEY (guild_id, map)
        );
        """)


async def db():
    return pool


async def get_flags(guild_id, map_key):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM flags WHERE guild_id=$1 AND map=$2",
            guild_id, map_key
        )


async def set_flag(guild_id, map_key, flag, status, role_id=None):
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO flags VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT DO UPDATE SET status=$4, role_id=$5
        """, guild_id, map_key, flag, status, role_id)


async def release_flag(guild_id, map_key, flag):
    await set_flag(guild_id, map_key, flag, "AVAILABLE", None)
