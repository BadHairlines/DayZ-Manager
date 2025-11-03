import discord
from cogs import utils  # ✅ use the full utils module now


# ======================================================
# 🧩 Ensure Faction Table Exists
# ======================================================
async def ensure_faction_table():
    """Ensure factions table exists (safe to call multiple times)."""
    if utils.db_pool is None:
        print("⚠️ Database pool not initialized — skipping faction table creation.")
        return

    async with utils.db_pool.acquire() as conn:
        # ✅ Create or verify the table
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
                claimed_flag TEXT,              -- ✅ Stores claimed flag name
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (guild_id, faction_name)
            );
        """)

        # ✅ Ensure backward compatibility with older schemas
        await conn.execute("""
            ALTER TABLE factions ADD COLUMN IF NOT EXISTS claimed_flag TEXT;
        """)

        # ✅ Optional data cleanup: normalize map values to lowercase
        try:
            await conn.execute("""
                UPDATE factions
                SET map = LOWER(map)
                WHERE map != LOWER(map);
            """)
            print("🧩 Normalized existing faction map entries to lowercase.")
        except Exception as e:
            print(f"⚠️ Could not normalize faction map names: {e}")

    print("✅ Verified factions table exists (with claimed_flag column).")


# ======================================================
# 🎨 Embed Helpers
# ======================================================
def make_embed(title: str, desc: str, color: int = 0x2ECC71) -> discord.Embed:
    """Helper to create embeds with consistent faction style."""
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_author(name="🎭 Faction Manager")
    embed.set_footer(
        text="DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    embed.timestamp = discord.utils.utcnow()
    return embed


def make_log_embed(action: str, details: str, user: discord.Member, color: int = 0xF1C40F) -> discord.Embed:
    """
    Helper to create log embeds for faction events.
    Example: creation, deletion, member added/removed.
    """
    embed = discord.Embed(
        title=f"🪵 {action}",
        description=details,
        color=color
    )
    embed.set_author(name=f"Action by {user.display_name}", icon_url=user.display_avatar.url)
    embed.set_footer(
        text="Faction Logs • DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    embed.timestamp = discord.utils.utcnow()
    return embed
