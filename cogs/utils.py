import discord  # keep this at the top of utils.py

async def log_faction_action(
    guild: discord.Guild,
    action: str,
    faction_name: str | None,
    user: discord.Member,
    details: str,
    map_key: str,
):
    """Write a faction log entry to DB and post an embed to the map-specific logs channel."""
    # Ensure DB
    await ensure_connection()

    mk = (map_key or "").strip().lower()
    full_details = f"[map: {mk}] {details}" if mk else details

    # 1) Always persist to DB (so we never lose the audit trail)
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
                VALUES ($1, $2, $3, $4, $5);
                """,
                str(guild.id), action, faction_name, str(user.id), full_details
            )
    except Exception as e:
        # Still try to notify in Discord even if DB write failed
        print(f"⚠️ Failed to insert faction_logs row: {e}")

    # 2) Try to find/create a place to post the embed
    log_channel: discord.TextChannel | None = None

    # Try category + channel by name first
    try:
        category = discord.utils.get(guild.categories, name="📜 DayZ Manager Logs")
        if category is None:
            try:
                category = await guild.create_category(
                    "📜 DayZ Manager Logs",
                    reason="Auto-created for faction logs"
                )
            except discord.Forbidden:
                category = None  # fall back below

        channel_name = f"factions-{mk}-logs" if mk else "factions-logs"
        log_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if log_channel is None and category is not None:
            try:
                log_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    reason="Auto-created map-specific faction log channel",
                )
                try:
                    await log_channel.send(
                        f"🪵 This channel logs faction activity for **{mk.title() if mk else 'all maps'}**."
                    )
                except Exception:
                    pass
            except discord.Forbidden:
                log_channel = None
    except Exception as e:
        print(f"⚠️ Error while resolving faction log channel: {e}")

    # Fallback: try system channel if we couldn’t create/use our preferred one
    if log_channel is None:
        log_channel = guild.system_channel

    # 3) Build the embed
    al = (action or "").lower()
    if "create" in al:
        color = 0x2ECC71
    elif "delete" in al or "disband" in al:
        color = 0xE74C3C
    elif "update" in al or "edit" in al:
        color = 0xF1C40F
    else:
        color = 0x3498DB

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

    # 4) Try to send; if we have absolutely nowhere to send, just swallow (DB already has the record)
    if log_channel is not None:
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("⚠️ No permission to send to the resolved log channel.")
        except Exception as e:
            print(f"⚠️ Failed to send faction log embed: {e}")
    else:
        print("ℹ️ No available log channel (and no system channel). Embed not sent.")
