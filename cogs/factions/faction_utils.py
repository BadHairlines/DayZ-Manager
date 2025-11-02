import discord
from cogs import utils

async def ensure_faction_table():
    if utils.db_pool is None: return
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
                claimed_flag TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (guild_id, faction_name)
            );
        """)
        await conn.execute("ALTER TABLE factions ADD COLUMN IF NOT EXISTS claimed_flag TEXT;")

def make_embed(title:str, desc:str, color:int=0x2ECC71)->discord.Embed:
    e=discord.Embed(title=title, description=desc, color=color)
    e.set_author(name="Faction Manager")
    e.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    e.timestamp=discord.utils.utcnow()
    return e

def make_log_embed(action:str, details:str, user:discord.Member, color:int=0xF1C40F)->discord.Embed:
    e=discord.Embed(title=action, description=details, color=color)
    e.set_author(name=f"Action by {user.display_name}", icon_url=user.display_avatar.url)
    e.set_footer(text="Faction Logs • DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
    e.timestamp=discord.utils.utcnow()
    return e
