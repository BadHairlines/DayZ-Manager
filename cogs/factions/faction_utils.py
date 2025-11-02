import discord
from cogs.utils import db_pool

async def ensure_faction_table():
    """Ensure factions table exists."""
    if db_pool is None:
        print("⚠️ db_pool not initialized — skipping table creation.")
        return
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS factions (
                id SERIAL PRIMARY KEY,
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

def make_embed(title, desc, color=0x2ECC71):
    """Helper to create embeds with consistent style."""
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_author(name="🎭 Faction Manager")
    embed.set_footer(
        text="DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    return embed
