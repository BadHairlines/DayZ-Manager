import discord  # make sure this import exists at the top of utils.py

async def log_faction_action(
    guild: discord.Guild,
    action: str,
    faction_name: str | None,
    user: discord.Member,
    details: str,
    map_key: str,  # 👈 NEW: which map this log belongs to (e.g. "livonia")
):
    """Record faction actions to DB and send a formatted embed to a map-specific faction log channel."""
    require_db()

    # ✅ Normalize map key (expected: "livonia", "chernarus", "sakhal")
    mk = (map_key or "").strip().lower()

    # 🧩 Save to DB (schema unchanged; map included in details for history)
    full_details = f"[map: {mk}] {details}" if mk else details
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
            VALUES ($1, $2, $3, $4, $5);
            """,
            str(guild.id),
            action,
            faction_name,
            str(user.id),
            full_details,
        )

    # 📂 Ensure the universal logs category exists
    logs_category_name = "📜 DayZ Manager Logs"
    category = discord.utils.get(guild.categories, name=logs_category_name)
    if not category:
        category = await guild.create_category(
            logs_category_name, reason="Auto-created for faction logs"
        )

    # 🪵 Map-specific faction log channel
    channel_basename = f"factions-{mk}-logs" if mk else "factions-logs"
    log_channel = discord.utils.get(guild.text_channels, name=channel_basename)
    if not log_channel:
        log_channel = await guild.create_text_channel(
            name=channel_basename,
            category=category,
            reason="Auto-created map-specific faction log channel",
        )
        try:
            await log_channel.send(
                f"🪵 This channel logs faction activity for **{mk.title() if mk else 'all maps'}**."
            )
        except Exception:
            pass

    # 🎨 Color by action
    al = action.lower()
    if "create" in al:
        color = 0x2ECC71  # green
    elif "delete" in al or "disband" in al:
        color = 0xE74C3C  # red
    elif "update" in al or "edit" in al:
        color = 0xF1C40F  # yellow
    else:
        color = 0x3498DB  # blue (default)

    # ✨ Build embed
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
    embed.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
    embed.set_footer(text=f"Faction Logs • {guild.name}")
    embed.timestamp = discord.utils.utcnow()

    # 🚀 Send embed
    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Failed to send faction log to #{channel_basename}: {e}")
