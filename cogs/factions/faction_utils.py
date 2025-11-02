import discord
from cogs import utils  # ✅ use the full utils module now

async def ensure_faction_table():
    """Ensure factions table exists (safe to call multiple times)."""
    # 🧩 Double safety: ensure DB is ready before touching it
    if utils.db_pool is None:
        print("⚠️ Database pool not initialized — skipping faction table creation.")
        return

    async with utils.db_pool.acquire() as conn:
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
    print("✅ Verified factions table exists.")


def make_embed(title: str, desc: str, color: int = 0x2ECC71) -> discord.Embed:
    """Helper to create embeds with consistent faction style."""
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_author(name="🎭 Faction Manager")
    embed.set_footer(
        text="DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    return embed
