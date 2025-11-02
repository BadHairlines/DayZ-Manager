import discord
from discord.ext import commands
from cogs.utils import db_pool, MAP_DATA, create_flag_embed
import asyncio


class AutoRefresh(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_flag_message(self, guild: discord.Guild, map_key: str):
        """Safely refresh an existing flag message — recreate only if truly missing."""
        guild_id = str(guild.id)

        # 🧩 Check if this map is even set up
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )

        if not row:
            print(f"⏭️ Skipping {MAP_DATA[map_key]['name']} for {guild.name} (not set up yet).")
            return

        channel_id = int(row["channel_id"])
        message_id = int(row["message_id"])

        # 🧩 Try to find the stored channel
        channel = guild.get_channel(channel_id)
        if not channel:
            print(f"⚠️ Channel {channel_id} missing for {guild.name} ({MAP_DATA[map_key]['name']}).")
            try:
                # Recreate channel only if truly missing
                channel = await guild.create_text_channel(
                    name=f"flags-{map_key}",
                    reason=f"Recreated automatically for {MAP_DATA[map_key]['name']} flags"
                )
                await channel.send(
                    f"📜 This channel displays flag ownership for **{MAP_DATA[map_key]['name']}**."
                )
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE flag_messages SET channel_id=$1 WHERE guild_id=$2 AND map=$3",
                        str(channel.id), guild_id, map_key
                    )
                print(f"🆕 Recreated missing channel: #{channel.name} in {guild.name}")
            except Exception as e:
                print(f"❌ Failed to recreate channel for {guild.name} ({map_key}): {e}")
                return

        # 🧩 Try to fetch the existing message and update the embed
        embed = await create_flag_embed(guild_id, map_key)
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=embed)
            print(f"🔄 Refreshed flag display for {guild.name} - {MAP_DATA[map_key]['name']}")
        except discord.NotFound:
            # Message no longer exists — recreate and update DB
            msg = await channel.send(embed=embed)
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE flag_messages SET message_id=$1 WHERE guild_id=$2 AND map=$3",
                    str(msg.id), guild_id, map_key
                )
            print(f"♻️ Recreated missing flag message for {guild.name} - {MAP_DATA[map_key]['name']}")
        except discord.Forbidden:
            print(f"⚠️ Missing permission to edit flag message in {guild.name} - {MAP_DATA[map_key]['name']}")
        except Exception as e:
            print(f"⚠️ Unexpected error updating message for {guild.name} - {MAP_DATA[map_key]['name']}: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-refresh all stored flag messages after bot startup."""
        await self.bot.wait_until_ready()
        print("🚀 DayZ Manager starting flag auto-refresh & recovery...")

        await asyncio.sleep(5)  # small delay for safety

        for guild in self.bot.guilds:
            guild_id = str(guild.id)

            try:
                # ✅ Only refresh maps that actually exist in the DB
                async with db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT map FROM flag_messages WHERE guild_id=$1",
                        guild_id
                    )

                if not rows:
                    print(f"⚠️ No maps set up for {guild.name}. Skipping auto-refresh.")
                    continue

                for row in rows:
                    await self.ensure_flag_message(guild, row["map"])
                    await asyncio.sleep(1)  # prevent rate limits

            except Exception as e:
                print(f"⚠️ Error during refresh for {guild.name}: {e}")

        print("✅ DayZ Manager finished auto-refresh & recovery of flag messages.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
