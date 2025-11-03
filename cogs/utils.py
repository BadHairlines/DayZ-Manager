async def log_faction_action(
    guild: discord.Guild,
    action: str,
    faction_name: str | None,
    user: discord.Member,
    details: str
):
    """Record faction actions to DB and send a formatted embed to #factions-logs."""
    require_db()

    # 🧩 Save to DB
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO faction_logs (guild_id, action, faction_name, user_id, details)
            VALUES ($1, $2, $3, $4, $5);
        """, str(guild.id), action, faction_name, str(user.id), details)

    # 🪵 Ensure category & log channel exist
    logs_category_name = "📜 DayZ Manager Logs"
    category = discord.utils.get(guild.categories, name=logs_category_name)
    if not category:
        category = await guild.create_category(logs_category_name, reason="Auto-created for faction logs")

    log_channel = discord.utils.get(guild.text_channels, name="factions-logs")
    if not log_channel:
        log_channel = await guild.create_text_channel(
            name="factions-logs",
            category=category,
            reason="Auto-created general faction log channel"
        )
        await log_channel.send("🪵 This channel logs all faction-related actions.")

    # 🎨 Dynamic color based on action type
    action_lower = action.lower()
    if "create" in action_lower:
        color = 0x2ECC71  # Green
    elif "delete" in action_lower or "disband" in action_lower:
        color = 0xE74C3C  # Red
    elif "update" in action_lower or "edit" in action_lower:
        color = 0xF1C40F  # Yellow
    else:
        color = 0x3498DB  # Blue (default)

    # ✨ Build clean structured embed
    embed = discord.Embed(
        title=f"🪵 {action}",
        color=color
    )
    if faction_name:
        embed.add_field(name="🏳️ Faction", value=f"**{faction_name}**", inline=True)
    embed.add_field(name="👤 Action By", value=user.mention, inline=True)
    embed.add_field(name="🕓 Timestamp", value=f"<t:{int(discord.utils.utcnow().timestamp())}:f>", inline=False)
    embed.add_field(name="📋 Details", value=details, inline=False)

    embed.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
    embed.set_footer(text=f"Faction Logs • {guild.name}")
    embed.timestamp = discord.utils.utcnow()

    # 🚀 Send embed safely
    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Failed to send faction log: {e}")
