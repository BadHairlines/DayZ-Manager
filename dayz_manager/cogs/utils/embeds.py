import discord
from dayz_manager.config import MAP_DATA
from .database import db_pool, require_db

async def create_flag_embed(guild_id: str, map_key: str) -> discord.Embed:
    require_db()
    async with db_pool.acquire() as conn:
        records = await conn.fetch(
            "SELECT flag, status, role_id FROM flags WHERE guild_id=$1 AND map=$2 ORDER BY flag ASC;",
            guild_id, map_key
        )

    embed = discord.Embed(title=f"🏴 Flag Ownership — {MAP_DATA[map_key]['name']}", color=0x3498DB)
    embed.set_image(url=MAP_DATA[map_key]["image"])
    embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")

    lines = []
    for row in records:
        role_id = row["role_id"]
        if role_id:
            lines.append(f"❌ **{row['flag']}** — <@&{role_id}>")
        else:
            lines.append(f"✅ **{row['flag']}** — *Unclaimed*")

    embed.description = "\n".join(lines) or "_No flags found._"
    return embed
