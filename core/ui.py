import discord
from core.flags import get_flags, MAP_DATA


async def build_embed(guild_id: str, map_key: str):
    rows = await get_flags(guild_id, map_key)
    map_info = MAP_DATA.get(map_key, {"name": map_key})

    embed = discord.Embed(
        title=f"🏴 {map_info['name']} Flags",
        color=0x3498DB
    )

    lines = []
    for r in rows:
        if r["role_id"]:
            lines.append(f"❌ {r['flag']} → <@&{r['role_id']}>")
        else:
            lines.append(f"✅ {r['flag']} — Free")

    embed.description = "\n".join(lines)
    return embed
