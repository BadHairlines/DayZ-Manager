import asyncpg
import ssl
import asyncio
from dayz_manager.config import DATABASE_URL

db_pool: asyncpg.Pool | None = None

async def ensure_connection():
    global db_pool
    if db_pool is None:
        await init_db()
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1;")
    except Exception:
        await init_db()

async def init_db():
    global db_pool
    if db_pool is not None:
        print("⚙️ Database pool already initialized.")
        return

    if not DATABASE_URL:
        raise RuntimeError("❌ DATABASE_URL not set in environment!")

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    print("🔌 Connecting to PostgreSQL…")
    for attempt in range(3):
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL, ssl=ssl_ctx)
            break
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"⚠️ Connection failed (attempt {attempt+1}/3): {e}")
            await asyncio.sleep(wait)
    else:
        raise RuntimeError("❌ Could not connect to PostgreSQL after 3 attempts.")

    async with db_pool.acquire() as conn:
        try:
            await conn.execute("""                CREATE TABLE IF NOT EXISTS flags (
                    guild_id TEXT NOT NULL,
                    map TEXT NOT NULL,
                    flag TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '✅',
                    role_id TEXT,
                    PRIMARY KEY (guild_id, map, flag)
                );
            """)

            await conn.execute("""                CREATE TABLE IF NOT EXISTS flag_messages (
                    guild_id TEXT NOT NULL,
                    map TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    log_channel_id TEXT,
                    PRIMARY KEY (guild_id, map)
                );
            """)

            await conn.execute("""                CREATE TABLE IF NOT EXISTS factions (
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

            await conn.execute("""                CREATE TABLE IF NOT EXISTS faction_logs (
                    id BIGSERIAL PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    faction_name TEXT,
                    user_id TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT NOW()
                );
            """)
            print("✅ Database tables verified successfully.")
        except Exception as e:
            print(f"❌ Database migration error: {e}")
            raise

    print("✅ PostgreSQL connected and ready (Flags + Factions + Logs).")


def require_db():
    if db_pool is None:
        raise RuntimeError("❌ Database not initialized yet.")
