import asyncpg
import os
import ssl
import discord

# ======================================================
# 🗃 Database connection pool
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

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("❌ DATABASE_URL not found in environment variables!")

    # ✅ Always use SSL (safe for both internal & external Railway URLs)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # ✅ Create connection pool
    db_pool = await asyncpg.create_pool(db_url, ssl=ssl_ctx)

    async with db_pool.acquire() as conn:
        # Create flags table if missing
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

        # Create flag_messages table if missing
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flag_messages (
                guild_id TEXT NOT NULL,
                map TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, map)
            );
        """)

        # ✅ Auto-add log_channel_id column if missing (self-healing schema)
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='flag_messages' AND column_name='log_channel_id'
                ) THEN
                    ALTER TABLE flag_messages ADD COLUMN log_channel_id TEXT;
                END IF;
            END $$;
        """)

    print("✅ Connected to PostgreSQL and ensured all tables/columns exist.")


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
        return await conn.fetchrow("""
            SELECT status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2 AND flag=$3
        """, guild_id, map_name, flag)


async def get_all_flags(guild_id: str, map_name: str):
    """Fetch all flags for a specific map."""
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT flag, status, role_id FROM flags
            WHERE guild_id=$1 AND map=$2
        """, guild_id, map_name)


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


# ======================================================
# 🧱 Shared Flag Embed Builder
# ======================================================
async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    """Generate an embed showing all flags and their statuses for a map."""
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
        emoji = CUSTOM_EMOJIS.get(flag, "")
        if not emoji.startswith("<:"):
            emoji = ""
        display_value = "✅" if status == "✅" else (f"<@&{role_id}>" if role_id else "❌")
        lines.append(f"{emoji} **• {flag}**: {display_value}")

    embed.description = "\n".join(lines)
    return embed


# ======================================================
# 🪵 Shared Logging Function (Embed Version)
# ======================================================
async def log_action(guild: discord.Guild, map_key: str, message: str):
    """
    Send a log message as an embed to the map's assigned log channel.
    Automatically formats messages with color and timestamp.
    """
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

    # 🟩 Pick color based on context
    lower_msg = message.lower()
    if "assigned" in lower_msg or "released" in lower_msg:
        color = 0x2ECC71  # green
    elif "cleanup" in lower_msg:
        color = 0x95A5A6  # gray
    elif "failed" in lower_msg or "error" in lower_msg:
        color = 0xE74C3C  # red
    else:
        color = 0xF1C40F  # yellow (warning/info)

    # 🧱 Build embed
    embed = discord.Embed(
        title=f"🪵 {MAP_DATA[map_key]['name']} Log",
        description=message,
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
# 🧹 Auto-Cleanup of Deleted Roles
# ======================================================
async def cleanup_deleted_roles(guild: discord.Guild):
    """
    Checks all flags assigned to roles that no longer exist in the guild.
    Automatically resets those flags back to ✅ and logs each cleanup action.
    """
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
            map_key = row["map"]
            flag = row["flag"]
            role_id = row["role_id"]

            if not guild.get_role(int(role_id)):  # Role deleted from server
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
                    f"🧹 **Auto-Cleanup:** `{flag}` reset to ✅ — deleted role <@&{role_id}> was removed."
                )

    if cleaned_count > 0:
        print(f"✅ Auto-Cleanup complete: {cleaned_count} cleaned in {guild.name}")
