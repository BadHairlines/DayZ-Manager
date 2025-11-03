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


# ======================================================
# ⚙️ Flag CRUD Operations
# ======================================================
async def set_flag(guild_id: str, map_name: str, flag: str, status: str, role_id: str | None):
    await ensure_connection()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET status = EXCLUDED.status, role_id = EXCLUDED.role_id;
        """, guild_id, map_name, flag, status, role_id)


async def get_flag(guild_id: str, map_name: str, flag: str):
    await ensure_connection()
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2 AND flag=$3
        """, guild_id, map_name, flag)


async def get_all_flags(guild_id: str, map_name: str):
    await ensure_connection()
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT flag, status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2
        """, guild_id, map_name)


async def release_flag(guild_id: str, map_name: str, flag: str):
    await set_flag(guild_id, map_name, flag, "✅", None)


async def reset_map_flags(guild_id: str, map_name: str):
    await ensure_connection()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE flags
            SET status='✅', role_id=NULL
            WHERE guild_id=$1 AND map=$2;
        """, guild_id, map_name)
        await conn.execute("""
            UPDATE factions
            SET claimed_flag=NULL
            WHERE guild_id=$1 AND map=$2;
        """, guild_id, map_name)


# ======================================================
# 🧭 Faction ↔ Flag Sync Utilities
# ======================================================
async def sync_faction_claims(guild_id: str):
    await ensure_connection()
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT f.map, f.flag, f.role_id
            FROM flags f
            WHERE f.role_id IS NOT NULL AND f.guild_id=$1
        """, guild_id)
        for row in rows:
            await conn.execute("""
                UPDATE factions
                SET claimed_flag=$1
                WHERE guild_id=$2 AND role_id=$3 AND map=$4
            """, row["flag"], guild_id, row["role_id"], row["map"])
    print(f"🔁 Faction claims synced successfully for guild {guild_id}.")


async def get_faction_by_flag(guild_id: str, flag: str):
    await ensure_connection()
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM factions WHERE guild_id=$1 AND claimed_flag=$2",
            guild_id, flag
        )


# ======================================================
# 🧱 Shared Flag Embed Builder
# ======================================================
async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    await ensure_connection()
    records = await get_all_flags(guild_id, map_key)
    db_flags = {r["flag"]: r for r in records}

    embed = discord.Embed(
        title=f"**———⛳️ {MAP_DATA[map_key]['name'].upper()} FLAGS ⛳️———**",
        color=0x86DC3D
    )
    embed.set_author(name="🚨 Flags Notification 🚨")
    embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    embed.timestamp = discord.utils.utcnow()

    lines = []
    for flag in FLAGS:
        data = db_flags.get(flag)
        status = data["status"] if data else "✅"
        role_id = data["role_id"] if data and data["role_id"] else None
        display_value = "✅" if status == "✅" else (f"<@&{role_id}>" if role_id else "❌")
        lines.append(f"**• {flag}**: {display_value}")

    embed.description = "\n".join(lines)
    return embed


# ======================================================
# 🪵 Structured Logging (Flag System)
# ======================================================
async def log_action(guild: discord.Guild, map_key: str, title="Event Log", description="", color=None):
    await ensure_connection()
    guild_id = str(guild.id)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT log_channel_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
            guild_id, map_key
        )

    if not row or not row["log_channel_id"]:
        print(f"⚠️ No log channel found for {guild.name} ({map_key})")
        return

    log_channel = guild.get_channel(int(row["log_channel_id"]))
    if not log_channel:
        print(f"⚠️ Log channel deleted or invalid for {guild.name} ({map_key})")
        return

    if color is None:
        text = f"{title} {description}".lower()
        if any(word in text for word in ["assign", "release", "setup complete"]):
            color = 0x2ECC71
        elif "cleanup" in text:
            color = 0x95A5A6
        elif any(word in text for word in ["fail", "error"]):
            color = 0xE74C3C
        else:
            color = 0xF1C40F

    embed = discord.Embed(
        title=f"🪵 {MAP_DATA[map_key]['name']} | {title}",
        description=description,
        color=color
    )
    embed.set_thumbnail(url=MAP_DATA[map_key]["image"])
    embed.set_footer(
        text="DayZ Manager Logs",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    embed.timestamp = discord.utils.utcnow()

    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Failed to send embed log for {guild.name} ({map_key}): {e}")
