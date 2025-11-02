import discord
from discord.ext import commands
from cogs.utils import db_pool, MAP_DATA, create_flag_embed
import asyncio


class AutoRefresh(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_flag_channel(self, guild: discord.Guild, map_key: str):
        """Ensure a flag channel exists; create it if missing."""
        channel_name = f"flags-{map_key}"
        channel = discord.utils.get(guild.text_channels, name=channel_name)

        # ✅ Only create the channel if it already exists in DB
        if not channel:
            channel = await guild.create_text_channel(
                name=channel_name,
                reason=f"Auto-created by DayZ Manager for {MAP_DATA[map_key]['name']} flags"
            )
            await channel.send(
                f"📜 This channel displays flag ownership for **{MAP_DATA[map_key]['name']}**."
            )
            print(f"🆕 Created new channel: #{channel_name} in {guild.name}")

        return channel

    async def ensure_flag_message(self, guild: discord.Guild, map_key: str):
        """Ensure the flag message exists; recreate it if missing."""
        guild_id = str(guild.id)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )

        # ❌ If no database record exists, skip — map not set up yet
        if not row:
            print(f"⏭️ Skipping {MAP_DATA[map_key]['name']} for {guild.name} (not set up yet).")
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            # If channel was deleted, try recreating
            channel = await self.ensure_flag_channel(guild, map_key)

        embed = await create_flag_embed(guild_id, map_key)

        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            await msg.edit(embed=embed)
            print(f"🔄 Refreshed flags for {guild.name} - {MAP_DATA[map_key]['name']}")
        except Exception:
            # Message missing — recreate it
            msg = await channel.send(embed=embed)
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE flag_messages
                    SET channel_id=$1, message_id=$2
                    WHERE guild_id=$3 AND map=$4;
                """, str(channel.id), str(msg.id), guild_id, map_key)
            print(f"♻️ Recreated missing flag message for {guild.name} - {MAP_DATA[map_key]['name']}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-refresh only stored flag messages after bot startup."""
        await self.bot.wait_until_ready()
        print("🚀 DayZ Manager starting flag auto-refresh & recovery...")

        await asyncio.sleep(5)  # slight delay for stability

        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            try:
                # ✅ Fetch only existing map records for this guild
                async with db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT map FROM flag_messages WHERE guild_id = $1",
                        guild_id
                    )

                if not rows:
                    print(f"⚠️ No maps set up yet for {guild.name} — skipping auto-refresh.")
                    continue

                for row in rows:
                    map_key = row["map"]
                    await self.ensure_flag_message(guild, map_key)
                    await asyncio.sleep(1)  # prevent rate limits

            except Exception as e:
                print(f"⚠️ Error during refresh for {guild.name}: {e}")

        print("✅ DayZ Manager finished auto-refresh & recovery of flag messages.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
