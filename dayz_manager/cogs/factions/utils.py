import discord
from dayz_manager.cogs.utils.database import db_pool

async def ensure_faction_table():
    if db_pool is None:
        print("⚠️ Database pool not initialized — skipping faction table creation.")
        return

    async with db_pool.acquire() as conn:
        await conn.execute("""            CREATE TABLE IF NOT EXISTS factions (
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
        await conn.execute("ALTER TABLE factions ADD COLUMN IF NOT EXISTS claimed_flag TEXT;")
        try:
            await conn.execute("UPDATE factions SET map = LOWER(map) WHERE map != LOWER(map);")
            print("🧩 Normalized existing faction map entries to lowercase.")
        except Exception as e:
            print(f"⚠️ Could not normalize faction map names: {e}")

    print("✅ Verified factions table exists (with claimed_flag column).")


def make_embed(title: str, desc: str, color: int = 0x2ECC71) -> discord.Embed:
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_author(name="🎭 Faction Manager")
    embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    embed.timestamp = discord.utils.utcnow()
    return embed
