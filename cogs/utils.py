import asyncpg
import os
import ssl

# Database connection pool
db_pool: asyncpg.Pool | None = None

FLAGS = [
    "Altis", "APA", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals", "CDF",
    "CHEL", "Chedaki", "Chernarus", "CMC", "Crook", "DayZ", "HunterZ", "NAPA",
    "Livonia", "LivoniaArmy", "LivoniaPolice", "NSahrani", "Pirates", "Rex",
    "Refuge", "Rooster", "RSTA", "Snake", "SSahrani", "TEC", "UEC", "Wolf",
    "Zagorky", "Zenit"
]

MAP_DATA = {
    "livonia": {"name": "Livonia", "image": "https://i.postimg.cc/QN9vfr9m/Livonia.jpg"},
    "chernarus": {"name": "Chernarus", "image": "https://i.postimg.cc/3RWzMsLK/Chernarus.jpg"},
    "sakhal": {"name": "Sakhal", "image": "https://i.postimg.cc/HkBSpS8j/Sakhal.png"},
}

CUSTOM_EMOJIS = {flag: f":{flag}:" for flag in FLAGS}


# ======================================================
# 🧩 Database Initialization
# ======================================================
async def init_db():
    """Initialize PostgreSQL connection and ensure the table exists."""
    global db_pool

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("❌ DATABASE_URL not found in environment variables!")

    # ⚙️ Choose SSL settings dynamically
    ssl_ctx = None
    if "railway.internal" not in db_url:
        # External connection → enable SSL (disable hostname verification)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    # ✅ Create connection pool
    db_pool = await asyncpg.create_pool(db_url, ssl=ssl_ctx)

    # ✅ Create table if missing
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flags (
                guild_id TEXT NOT NULL,
                map TEXT NOT NULL,
                flag TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '✅',
                role_id TEXT,
                PRIMARY KEY (guild_id, map, flag)
            );
        """)

    print("✅ Connected to PostgreSQL and ensured flags table exists.")


# ======================================================
# ⚙️ CRUD Operations
# ======================================================
async def set_flag(guild_id: str, map_name: str, flag: str, status: str, role_id: str | None):
    """Insert or update a flag record."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET status = EXCLUDED.status, role_id = EXCLUDED.role_id;
        """, guild_id, map_name, flag, status, role_id)


async def get_flag(guild_id: str, map_name: str, flag: str):
    """Fetch one flag record."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2 AND flag=$3
        """, guild_id, map_name, flag)
        return row


async def get_all_flags(guild_id: str, map_name: str):
    """Fetch all flags for a specific map."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT flag, status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2
        """, guild_id, map_name)
        return rows


async def release_flag(guild_id: str, map_name: str, flag: str):
    """Reset a flag to ✅ and clear the assigned role."""
    await set_flag(guild_id, map_name, flag, "✅", None)


async def reset_map_flags(guild_id: str, map_name: str):
    """Reset all flags for a map to ✅ and clear all roles."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE flags
            SET status='✅', role_id=NULL
            WHERE guild_id=$1 AND map=$2;
        """, guild_id, map_name)
