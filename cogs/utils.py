import asyncpg
import os
import ssl
import asyncio
import discord

# ======================================================
# 🗃️ Global Database Pool
# ======================================================
db_pool: asyncpg.Pool | None = None

# ======================================================
# 🏴 Official Flag & Map Data
# ======================================================
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

# ======================================================
# 🔁 Connection Guard
# ======================================================
async def ensure_connection():
    """Ensure db_pool exists and reconnect if lost."""
    global db_pool
    if db_pool is None:
        print("⚠️ DB pool not found — initializing...")
        await init_db()
        return

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1;")
    except Exception as e:
        print(f"⚠️ Lost DB connection, reconnecting: {e}")
        await init_db()

# ======================================================
# 🧩 Initialize Database
# ======================================================
async def init_db():
    """Connect to PostgreSQL and ensure all tables/columns exist."""
    global db_pool
    if db_pool is not None:
        print("⚙️ Database pool already initialized.")
        return

    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("PG_URL")
    if not db_url:
        raise RuntimeError("❌ DATABASE_URL not set in environment!")

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
            print(f"⚠️ Connection failed (attempt {attempt+1}/3): {e}")
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
            print("⚙️ Verifying factions table...")
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

            # ==========================
            # 📜 Faction Logs Table
            # ==========================
            print("⚙️ Verifying faction_logs table...")
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
            print("✅ Database tables verified successfully.")

        except Exception as e:
            print(f"❌ Database migration error: {e}")
            raise

    print("✅ PostgreSQL connected and ready (Flags + Factions + Logs).")

# ======================================================
# 🧰 Utility Safety Wrapper
# ======================================================
def require_db():
    if db_pool is None:
        raise RuntimeError("❌ Database not initialized yet.")

# ======================================================
# ⚙️ FLAG FUNCTIONS
# ======================================================
async def get_flag(guild_id: str, map_key: str, flag: str):
    require_db()
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM flags WHERE guild_id=$1 AND map=$2 AND flag=$3;",
            guild_id, map_key, flag
        )

async def get_all_flags(guild_id: str, map_key: str):
    require_db()
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM flags WHERE guild_id=$1 AND map=$2 ORDER BY flag ASC;",
            guild_id, map_key
        )

async def set_flag(guild_id: str, map_key: str, flag: str, status: str, role_id: str | None):
    require_db()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET
                status = EXCLUDED.status,
                role_id = EXCLUDED.role_id;
        """, guild_id, map_key, flag, status, role_id)

async def release_flag(guild_id: str, map_key: str, flag: str):
    require_db()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE flags
            SET status='✅', role_id=NULL
            WHERE guild_id=$1 AND map=$2 AND flag=$3;
        """, guild_id, map_key, flag)

# ======================================================
# 🧩 FACTION UTILITIES
# ======================================================
async def get_faction_by_flag(guild_id: str, flag: str):
    require_db()
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM factions WHERE guild_id=$1 AND claimed_flag=$2;",
            guild_id, flag
        )

# ======================================================
# 🧾 EMBEDS
# ======================================================
async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    require_db()
    async with db_pool.acquire() as conn:
        records = await conn.fetch(
            "SELECT flag, status, role_id FROM flags WHERE guild_id=$1 AND map=$2 ORDER BY flag ASC;",
            guild_id, map_key
        )

    embed = discord.Embed(
        title=f"🏴 Flag Ownership — {MAP_DATA[map_key]['name']}",
        color=0x3498DB
    )
    embed.set_image(url=MAP_DATA[map_key]["image"])
    embed.set_footer(
        text="DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )

    lines = []
    for row in records:
        role_id = row["role_id"]
        if role_id:
            lines.append(f"❌ **{row['flag']}** — <@&{role_id}>")
        else:
            lines.append(f"✅ **{row['flag']}** — *Unclaimed*")

    embed.description = "\n".join(lines) or "_No flags found._"
    return embed

# ======================================================
# 🪵 LOGGING
# ======================================================
async def log_action(guild: discord.Guild, map_key: str, title: str, description: str, color: int = 0x2ECC71):
    require_db()
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT log_channel_id FROM flag_messages WHERE guild_id=$1 AND map=$2;",
            str(guild.id), map_key
        )

    log_channel = guild.get_channel(int(row["log_channel_id"])) if row and row["log_channel_id"] else None
    if not log_channel:
        print(f"⚠️ Missing log channel for {guild.name}/{map_key}")
        return

    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = discord.utils.utcnow()
    embed.set_footer(text=f"Map: {MAP_DATA[map_key]['name']}")
    await log_channel.send(embed=embed)

async def log_faction_action(guild: discord.Guild, action: str, faction_name: str | None, user: discord.Member, details: str):
    require_db()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
            VALUES ($1, $2, $3, $4, $5);
        """, str(guild.id), action, faction_name, str(user.id), details)
