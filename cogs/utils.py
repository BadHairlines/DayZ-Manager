import asyncpg
import os
import ssl
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
# 🧩 Database Initialization
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
    try:
        db_pool = await asyncpg.create_pool(db_url, ssl=ssl_ctx)
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise

    async with db_pool.acquire() as conn:
        try:
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

    print("✅ Connected to PostgreSQL and ensured all tables/columns exist.")


# ======================================================
# ⚙️ Helpers
# ======================================================
def require_db():
    if db_pool is None:
        raise RuntimeError("❌ Database not initialized yet. Run init_db() first.")


# ======================================================
# ⚙️ Flag CRUD
# ======================================================
async def set_flag(guild_id, map_name, flag, status, role_id):
    require_db()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET status=EXCLUDED.status, role_id=EXCLUDED.role_id;
        """, guild_id, map_name, flag, status, role_id)


async def get_all_flags(guild_id, map_name):
    require_db()
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT flag, status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2
        """, guild_id, map_name)


async def reset_map_flags(guild_id, map_name):
    require_db()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE flags SET status='✅', role_id=NULL WHERE guild_id=$1 AND map=$2;
        """, guild_id, map_name)
        await conn.execute("""
            UPDATE factions SET claimed_flag=NULL WHERE guild_id=$1 AND map=$2;
        """, guild_id, map_name)


# ======================================================
# 🧱 Shared Flag Embed
# ======================================================
async def create_flag_embed(guild_id, map_key):
    require_db()
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
        display = "✅" if status == "✅" else (f"<@&{role_id}>" if role_id else "❌")
        lines.append(f"**• {flag}**: {display}")
    embed.description = "\n".join(lines)
    return embed


# ======================================================
# 🪵 Unified Logging (Flag + Faction)
# ======================================================
async def ensure_log_channel(guild: discord.Guild, map_key: str):
    """Ensure DayZ Manager category and log channel exist."""
    require_db()
    guild_id = str(guild.id)

    # ✅ Ensure category
    category_name = "DayZ Manager"
    manager_category = discord.utils.get(guild.categories, name=category_name)
    if not manager_category:
        manager_category = await guild.create_category(category_name)

    # ✅ Check existing DB entry
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT log_channel_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
            guild_id, map_key
        )

    log_channel = None
    if row and row["log_channel_id"]:
        log_channel = guild.get_channel(int(row["log_channel_id"]))

    # ✅ Rebuild if missing
    if not log_channel:
        logs_channel_name = f"{map_key}-flag-logs"
        log_channel = discord.utils.get(guild.text_channels, name=logs_channel_name)
        if not log_channel:
            log_channel = await guild.create_text_channel(
                name=logs_channel_name,
                category=manager_category,
                reason=f"Auto-created log channel for {map_key}"
            )
            await log_channel.send(f"🧾 Log channel created for **{map_key}** under {manager_category.name}.")
        else:
            if log_channel.category != manager_category:
                await log_channel.edit(category=manager_category)

        # ✅ Update DB
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE flag_messages SET log_channel_id=$1
                WHERE guild_id=$2 AND map=$3
            """, str(log_channel.id), guild_id, map_key)

    return log_channel


async def log_action(guild: discord.Guild, map_key: str, title="Event Log", description="", color=None):
    """Send a structured log embed to the correct DayZ Manager log channel."""
    log_channel = await ensure_log_channel(guild, map_key)
    if not log_channel:
        print(f"⚠️ Could not find or create log channel for {guild.name} ({map_key})")
        return

    if color is None:
        text = f"{title} {description}".lower()
        if "fail" in text or "error" in text:
            color = 0xE74C3C
        elif "assign" in text or "release" in text or "setup" in text:
            color = 0x2ECC71
        elif "cleanup" in text:
            color = 0x95A5A6
        else:
            color = 0xF1C40F

    embed = discord.Embed(
        title=f"🪵 {MAP_DATA[map_key]['name']} | {title}",
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=MAP_DATA[map_key]["image"])
    embed.set_footer(text="DayZ Manager Logs", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")

    await log_channel.send(embed=embed)


# ======================================================
# 📜 Faction Logs (also under DayZ Manager)
# ======================================================
async def log_faction_action(guild, action, faction_name=None, user=None, details=None):
    if db_pool is None:
        print("⚠️ Skipping faction log — DB not ready.")
        return

    # ✅ Ensure DayZ Manager category
    category_name = "DayZ Manager"
    manager_category = discord.utils.get(guild.categories, name=category_name)
    if not manager_category:
        manager_category = await guild.create_category(category_name)

    # ✅ Ensure #faction-logs channel
    log_channel = discord.utils.get(guild.text_channels, name="faction-logs")
    if not log_channel:
        log_channel = await guild.create_text_channel("faction-logs", category=manager_category)
        await log_channel.send(f"📜 Faction log channel created under {manager_category.name}.")

    # ✅ Write DB entry
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
            VALUES ($1, $2, $3, $4, $5)
        """, str(guild.id), action, faction_name, str(user.id) if user else None, details)

    color_map = {
        "create": 0x2ECC71,
        "delete": 0xE74C3C,
        "assign": 0xF1C40F,
        "update": 0x3498DB,
        "release": 0x95A5A6,
    }
    color = next((v for k, v in color_map.items() if k in action.lower()), 0x95A5A6)

    embed = discord.Embed(
        title=f"📜 Faction Log — {action}",
        description=(
            f"**Faction:** `{faction_name}`\n"
            f"**User:** {user.mention if user else '*System*'}\n"
            f"**Details:** {details or '*No details provided.*'}"
        ),
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="DayZ Manager • Faction Logs", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    await log_channel.send(embed=embed)


# ======================================================
# 🧹 Cleanup Deleted Roles
# ======================================================
async def cleanup_deleted_roles(guild):
    if not db_pool:
        print("⚠️ Database not initialized. Skipping cleanup.")
        return

    guild_id = str(guild.id)
    cleaned = 0
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT map, flag, role_id FROM flags
            WHERE guild_id=$1 AND role_id IS NOT NULL;
        """, guild_id)
        for row in rows:
            role = guild.get_role(int(row["role_id"]))
            if not role:
                await conn.execute("""
                    UPDATE flags SET status='✅', role_id=NULL
                    WHERE guild_id=$1 AND map=$2 AND flag=$3;
                """, guild_id, row["map"], row["flag"])
                await conn.execute("""
                    UPDATE factions SET claimed_flag=NULL WHERE guild_id=$1 AND role_id=$2;
                """, guild_id, str(row["role_id"]))
                cleaned += 1
                await log_action(
                    guild,
                    row["map"],
                    title="Auto-Cleanup",
                    description=f"🧹 `{row['flag']}` reset to ✅ — deleted role <@&{row['role_id']}> was removed."
                )
    if cleaned > 0:
        print(f"✅ Auto-cleanup complete: {cleaned} cleaned in {guild.name}")
