async def register_persistent_views():
    """Re-register saved flag panels for all guilds/maps from the DB."""
    FlagManageView = resolve_flag_manage_view()
    if not FlagManageView or utils.db_pool is None:
        log.warning("⚠️ Cannot register persistent views — missing FlagManageView or DB pool.")
        return

    async with utils.db_pool.acquire() as conn:
        try:
            rows = await conn.fetch("SELECT guild_id, map, channel_id, message_id FROM flag_messages;")
        except Exception as e:
            log.info(f"ℹ️ No flag_messages table yet or DB fetch failed: {e}")
            return

    if not rows:
        log.info("ℹ️ No flag messages found to re-register.")
        return

    count = 0
    for row in rows:
        guild_id, map_key, channel_id, message_id = (
            int(row["guild_id"]),
            row["map"],
            int(row["channel_id"]),
            int(row["message_id"]),
        )
        guild = bot.get_guild(guild_id)
        if not guild:
            log.warning(f"⚠️ Guild {guild_id} not found in cache; skipping.")
            continue

        channel = guild.get_channel(channel_id)
        if not channel:
            log.warning(f"⚠️ Channel {channel_id} missing for {guild.name}/{map_key}; skipping.")
            continue

        try:
            # Confirm the message still exists before adding the view
            msg = await channel.fetch_message(message_id)
            if not msg:
                log.warning(f"⚠️ Message {message_id} not found in {guild.name}/{map_key}.")
                continue

            view = FlagManageView(guild, map_key, bot)
            bot.add_view(view, message_id=message_id)
            count += 1
            log.info(f"✅ Re-registered view for {guild.name} → {map_key.title()}")
        except discord.NotFound:
            log.warning(f"⚠️ Message {message_id} deleted in {guild.name}/{map_key}.")
        except Exception as e:
            log.warning(f"⚠️ Failed to re-register {guild.name}/{map_key}: {e}")

    log.info(f"🔄 Persistent views registered: {count}")
