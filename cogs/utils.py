import asyncpg
import os
import ssl
import asyncio
import discord

# ======================================================
# 🗃 Database connection pool (shared globally)
# ======================================================
db_pool: asyncpg.Pool | None = None

# ✅ Official 25 flags only
FLAGS = [
    "APA", "Altis", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals",
    "CHEL", "Chedaki", "CMC", "Crook", "HunterZ", "NAPA", "NSahrani",
    "Pirates", "Rex", "Refuge", "Rooster", "RSTA", "Snake",
    "TEC", "UEC", "Wolf", "Zagorky", "Zenit"
]

MAP_DATA = {
    "livonia": {"name": "Livonia", "image": "https://i.postimg.cc/QN9vfr9m/Livonia.jpg"},
    "chernarus": {"name": "Chernarus", "image": "https://i.postimg.cc/3RWzMsLK/Chernarus.jpg"},
    "sakhal": {"name": "Sakhal", "image": "https://i.postimg.cc/HkBSpS8j/Sakhal.png"},
}

CUSTOM_EMOJIS = {flag: f":{flag}:" for flag in FLAGS}


# ======================================================
# 🧠 Auto-Healing Connection Helper
# ======================================================
async def ensure_connection():
    """Ensure db_pool is alive and reconnect if lost."""
    global db_pool
    if db_pool is None:
        print("⚠️ DB pool not found — initializing...")
        await init_db()
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1;")
    except Exception as e:
        print(f"⚠️ Lost DB connection — reconnecting: {e}")
        await init_db()


# ======================================================
# 🧩 Database Initialization (with auto-migration + retries)
# ======================================================
async def init_db():
    """Initialize PostgreSQL connection and ensure all tables/columns exist."""
    global db_pool

    if db_pool is not None:
        print("⚙️ Database pool already initialized.")
        return

    db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("PG_URL")
    )
    if not db_url:
        raise RuntimeError("❌ DATABASE_URL not found in environment variables!")

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    print("🔌 Connecting to PostgreSQL…")
    for attempt in range(3):
        try:
            db_pool = await asyncpg.create_pool(db_url, ssl=ssl_ctx)
            break
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"⚠️ Database connection failed (attempt {attempt+1}/3): {e}")
            await asyncio.sleep(wait)
    else:
        raise RuntimeError("❌ Could not connect to PostgreSQL after 3 attempts.")

    async with db_pool.acquire() as conn:
        try:
            # ==========================
            # 🏁 Flags Tables
            # ==========================
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

            # ==========================
            # 🏴‍☠️ Factions Table
            # ==========================
            print("⚙️ Creating or verifying factions table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS factions (
                    id BIGSERIAL PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    map TEXT NOT NULL,
                    faction_name TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    leader_id TEXT NOT NULL,
                    member_ids TEXT[],
                    color TEXT,
                    claimed_flag TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (guild_id, faction_name)
                );
            """)
            col_check = await conn.fetchval("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='factions' AND column_name='claimed_flag';
            """)
            if not col_check:
                await conn.execute("ALTER TABLE factions ADD COLUMN claimed_flag TEXT;")
                print("🧩 Added missing column: claimed_flag → factions table.")
            print("✅ Factions table verified successfully.")

            # ==========================
            # 📜 Faction Logs Table
            # ==========================
            print("⚙️ Creating or verifying faction_logs table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS faction_logs (
                    id BIGSERIAL PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    faction_name TEXT,
                    user_id TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT NOW()
                );
            """)
            print("✅ Faction logs table verified successfully.")

        except Exception as e:
            print(f"❌ Database migration error: {e}")
            raise

    print("✅ Connected to PostgreSQL and ensured all tables/columns exist (Flags + Factions + Logs).")


# ======================================================
# ⚙️ Database Access Safety Helper
# ======================================================
def require_db():
    """Ensure the DB is initialized before any query."""
    if db_pool is None:
        raise RuntimeError("❌ Database not initialized yet. Run init_db() before using DB functions.")
