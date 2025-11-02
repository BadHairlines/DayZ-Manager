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
# 🧩 Database Initialization (with auto-migration)
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
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (guild_id, faction_name)
                );
            """)
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
    require_db()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO flags (guild_id, map, flag, status, role_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, map, flag)
            DO UPDATE SET status = EXCLUDED.status, role_id = EXCLUDED.role_id;
        """, guild_id, map_name, flag, status, role_id)


async def get_flag(guild_id: str, map_name: str, flag: str):
    require_db()
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2 AND flag=$3
        """, guild_id, map_name, flag)


async def get_all_flags(guild_id: str, map_name: str):
    require_db()
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT flag, status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2
        """, guild_id, map_name)


async def release_flag(guild_id: str, map_name: str, flag: str):
    await set_flag(guild_id, map_name, flag, "✅", None)


async def reset_map_flags(guild_id: str, map_name: str):
    require_db()
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE flags
            SET status='✅', role_id=NULL
            WHERE guild_id=$1 AND map=$2;
        """, guild_id, map_name)


# ======================================================
# 🧱 Shared Flag Embed Builder
# ======================================================
async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
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
        display_value = "✅" if status == "✅" else (f"<@&{role_id}>" if role_id else "❌")
        lines.append(f"**• {flag}**: {display_value}")

    embed.description = "\n".join(lines)
    return embed


# ======================================================
# 🪵 Structured Logging (Flag System)
# ======================================================
async def log_action(guild: discord.Guild, map_key: str, title="Event Log", description="", color=None):
    require_db()
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


# ======================================================
# 📜 Faction Logging System
# ======================================================
async def log_faction_action(
    guild: discord.Guild,
    action: str,
    faction_name: str | None = None,
    user: discord.Member | None = None,
    details: str | None = None
):
    """Store faction actions in DB and send embed to #faction-logs."""
    if db_pool is None:
        print("⚠️ Skipping faction log — DB not ready.")
        return

    # 🧠 Save to database
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
            VALUES ($1, $2, $3, $4, $5)
        """, str(guild.id), action, faction_name, str(user.id) if user else None, details)

    # 🧾 Send embed to #faction-logs
    log_channel = discord.utils.get(guild.text_channels, name="faction-logs")
    if not log_channel:
        try:
            log_channel = await guild.create_text_channel("faction-logs", reason="Faction logging channel auto-created.")
            print(f"🆕 Created #faction-logs channel in {guild.name}")
        except Exception as e:
            print(f"⚠️ Could not create #faction-logs in {guild.name}: {e}")
            return

    color_map = {
        "create": 0x2ECC71,  # green
        "delete": 0xE74C3C,  # red
        "add": 0x3498DB,     # blue
        "remove": 0xE67E22,  # orange
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
    embed.set_footer(
        text="DayZ Manager • Faction Logs",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )

    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Failed to send faction log to {guild.name}: {e}")


# ======================================================
# 🧹 Auto-Cleanup of Deleted Roles
# ======================================================
async def cleanup_deleted_roles(guild: discord.Guild):
    if not db_pool:
        print("⚠️ Database not initialized. Skipping cleanup.")
        return

    guild_id = str(guild.id)
    cleaned_count = 0

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT map, flag, role_id FROM flags
            WHERE guild_id = $1 AND role_id IS NOT NULL;
        """, guild_id)

        for row in rows:
            map_key, flag, role_id = row["map"], row["flag"], row["role_id"]

            if not guild.get_role(int(role_id)):
                await conn.execute("""
                    UPDATE flags
                    SET status = '✅', role_id = NULL
                    WHERE guild_id = $1 AND map = $2 AND flag = $3;
                """, guild_id, map_key, flag)

                cleaned_count += 1
                print(f"🧹 Cleaned up deleted role {role_id} for flag {flag} ({map_key})")

                await log_action(
                    guild,
                    map_key,
                    title="Auto-Cleanup",
                    description=f"🧹 `{flag}` reset to ✅ — deleted role <@&{role_id}> was removed."
                )

    if cleaned_count > 0:
        print(f"✅ Auto-Cleanup complete: {cleaned_count} cleaned in {guild.name}")
