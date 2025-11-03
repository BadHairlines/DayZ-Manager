# --- Faction logging (paste into cogs/utils.py) --------------------------------
from typing import Optional
import discord

async def log_faction_action(
    guild: discord.Guild,
    action: str,
    faction_name: Optional[str],
    user: discord.Member,
    details: str,
    map_key: str,
) -> None:
    """
    Persist a faction action to the DB and post a rich embed to a map-specific log channel.
    Requires ensure_connection() and db_pool to be defined in this module.
    """
    # 1) Ensure DB connection/pool exists
    await ensure_connection()

    mk = (map_key or "").strip().lower()
    full_details = f"[map: {mk}] {details}" if mk else details

    # 2) Make sure the table exists (idempotent + cheap)
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS faction_logs (
                    id BIGSERIAL PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    faction_name TEXT,
                    user_id TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            await conn.execute(
                """
                INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
                VALUES ($1, $2, $3, $4, $5);
                """,
                str(guild.id), action, faction_name, str(user.id), full_details
            )
    except Exception as e:
        # If DB insert fails, we still try to post the Discord embed
        print(f"⚠️ Failed to write faction_logs row: {e}")

    # 3) Resolve a log channel (create category/channel if missing; fall back to system)
    log_channel: Optional[discord.TextChannel] = None
    try:
        category = discord.utils.get(guild.categories, name="📜 DayZ Manager Logs")
        if category is None:
            try:
                category = await guild.create_category(
                    "📜 DayZ Manager Logs",
                    reason="Auto-created for faction logs"
                )
            except discord.Forbidden:
                category = None  # continue without a dedicated category

        channel_name = f"factions-{mk}-logs" if mk else "factions-logs"
        log_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if log_channel is None and category is not None:
            try:
                log_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    reason="Auto-created map-specific faction log channel",
                )
                # Nice-to-have notice; ignore errors
                try:
                    scope = mk.title() if mk else "all maps"
                    await log_channel.send(f"🪵 This channel logs faction activity for **{scope}**.")
                except Exception:
                    pass
            except discord.Forbidden:
                log_channel = None
    except Exception as e:
        print(f"⚠️ Error resolving faction log channel: {e}")

    if log_channel is None:
        log_channel = guild.system_channel  # may be None too — that’s ok

    # 4) Build and send the embed (if any channel available)
    al = (action or "").lower()
    if "create" in al:
        color = 0x2ECC71  # green
    elif "delete" in al or "disband" in al:
        color = 0xE74C3C  # red
    elif "update" in al or "edit" in al:
        color = 0xF1C40F  # yellow
    else:
        color = 0x3498DB  # blue

    embed = discord.Embed(title=f"🪵 {action}", color=color)
    if faction_name:
        embed.add_field(name="🏳️ Faction", value=f"**{faction_name}**", inline=True)
    if mk:
        embed.add_field(name="🗺️ Map", value=mk.title(), inline=True)
    embed.add_field(name="👤 Action By", value=user.mention, inline=True)
    embed.add_field(
        name="🕓 Timestamp",
        value=f"<t:{int(discord.utils.utcnow().timestamp())}:f>",
        inline=False,
    )
    embed.add_field(name="📋 Details", value=details, inline=False)
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.set_footer(text=f"Faction Logs • {guild.name}")
    embed.timestamp = discord.utils.utcnow()

    if log_channel is not None:
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("⚠️ No permission to send to the resolved log channel.")
        except Exception as e:
            print(f"⚠️ Failed to send faction log embed: {e}")
    else:
        print("ℹ️ No available log channel (and no system channel). Embed not sent.")
# ---------------------------------------------------------------------------
