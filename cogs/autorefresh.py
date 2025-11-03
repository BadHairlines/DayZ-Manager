import asyncio
import discord
from discord.ext import commands
from cogs.utils import db_pool, MAP_DATA, create_flag_embed


class AutoRefresh(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_flag_message(self, guild: discord.Guild, map_key: str):
        """Refresh existing flag message for a given map without creating anything new."""
        guild_id = str(guild.id)

        if map_key not in MAP_DATA:
            print(f"⚠️ Skipping unknown map '{map_key}' for {guild.name}")
            return

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )

        if not row:
            print(f"⏭️ {MAP_DATA[map_key]['name']} not set up yet in {guild.name}.")
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            print(f"⚠️ Channel missing for {guild.name} ({MAP_DATA[map_key]['name']}); skipping refresh.")
            print(f"   💡 Run `/setup {MAP_DATA[map_key]['name']}` to rebuild it.")
            return

        embed = await create_flag_embed(guild_id, map_key)

        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            await msg.edit(embed=embed)
            print(f"🔄 Refreshed flag display for {guild.name} - {MAP_DATA[map_key]['name']}")
        except discord.NotFound:
            print(f"⚠️ Flag message missing for {guild.name} - {MAP_DATA[map_key]['name']}. Skipping.")
            print(f"   💡 Use `/setup {MAP_DATA[map_key]['name']}` to recreate it.")
        except discord.Forbidden:
            print(f"⚠️ Missing permission to edit flag message in {guild.name} - {MAP_DATA[map_key]['name']}")
        except Exception as e:
            print(f"⚠️ Unexpected error updating message for {guild.name} ({map_key}): {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Auto-refresh flag messages on bot startup (no channel creation)."""
        await self.bot.wait_until_ready()

        if getattr(self.bot, "_refresh_done", False):
            return
        self.bot._refresh_done = True

        print("🚀 DayZ Manager starting flag auto-refresh...")
        await asyncio.sleep(5)

        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            try:
                async with db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT map FROM flag_messages WHERE guild_id=$1",
                        guild_id
                    )

                if not rows:
                    print(f"⚠️ No maps set up for {guild.name}. Skipping.")
                    continue

                print(f"🔍 Found maps in DB for {guild.name}: {[r['map'] for r in rows]}")

                for row in rows:
                    await self.ensure_flag_message(guild, row["map"])
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"⚠️ Error during refresh for {guild.name}: {e}")

        print("✅ Auto-refresh complete (no channels or messages created).")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRefresh(bot))
