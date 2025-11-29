@bot.command()
async def restarts(ctx):
    from datetime import datetime, timezone

    # Current UTC time (Discord timestamps assume UTC)
    now = datetime.now(timezone.utc)
    hour = now.hour
    minute = now.minute
    second = now.second
    now_ts = int(now.timestamp())

    # Divide hour into 4-hour blocks
    quarter_hour = hour / 4
    quarter_hour_floor = int(quarter_hour)
    last_restart_hour = (quarter_hour_floor + 1) * 4

    # Convert 24 → 0 (midnight)
    if last_restart_hour == 24:
        last_restart_hour = 0

    # Seconds since midnight
    seconds_since_midnight = hour * 3600 + minute * 60 + second

    # Last restart UNIX timestamp
    last_restart_unix = now_ts + ((last_restart_hour * 3600) - seconds_since_midnight)

    # Next restart = last restart + 4 hours
    next_restart_unix = last_restart_unix + 14400

    # Build final message (no mentions)
    msg = (
        f"⏰ **__Last Restart__:** <t:{int(last_restart_unix)}:t> - "
        f"(<t:{int(last_restart_unix)}:R>)\n"
        f"⏰ **__Next Restart__:** <t:{int(next_restart_unix)}:t> - "
        f"(<t:{int(next_restart_unix)}:R>)"
    )

    await ctx.send(msg, allowed_mentions=discord.AllowedMentions.none())
