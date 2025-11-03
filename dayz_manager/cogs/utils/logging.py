import discord
from dayz_manager.config import MAP_DATA
from .database import db_pool, require_db

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
        await conn.execute(
            "INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details) VALUES ($1, $2, $3, $4, $5);", 
            str(guild.id), action, faction_name, str(user.id), details
        )
