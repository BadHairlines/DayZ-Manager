import os
import asyncio
import discord
from discord.ext import commands
from cogs import utils

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False


# -----------------------------
# DB connection helper
# -----------------------------
async def _acquire_conn():
    if hasattr(utils, "safe_acquire"):
        return utils.safe_acquire()

    class _PoolCtx:
        def __init__(self, pool):
            self.pool = pool
            self.conn = None

        async def __aenter__(self):
            if self.pool is None or getattr(self.pool, "_closed", False):
                self.pool = await utils.ensure_connection()
            self.conn = await self.pool.acquire()
            return self.conn

        async def __aexit__(self, exc_type, exc, tb):
            if self.conn:
                await self.pool.release(self.conn)

    return _PoolCtx(utils.db_pool)


# -----------------------------
# Persistent Flag Views ONLY
# (no faction logic)
# -----------------------------
async def register_persistent_views():
    try:
        from cogs.ui_views import FlagManageView
    except Exception:
        return

    await utils.ensure_connection()

    try:
        async with await _acquire_conn() as conn:
            rows = await conn.fetch(
                "SELECT guild_id, map, channel_id, message_id FROM flag_messages;"
            )
    except Exception:
        return

    if not rows:
        return

    for row in rows:
        try:
            guild = bot.get_guild(int(row["guild_id"]))
            if not guild:
                continue

            channel = guild.get_channel(int(row["channel_id"]))
            if not channel:
                continue

            msg = await channel.fetch_message(int(row["message_id"]))

            view = FlagManageView(guild, row["map"], bot)
            bot.add_view(view, message_id=msg.id)

        except discord.NotFound:
            pass
        except Exception:
            pass


# -----------------------------
# Cog Loader
# -----------------------------
SKIP_FILES = {
    "__init__.py",
    "utils.py",
    "ui_views.py",
}

async def load_cogs():
    loaded = 0
    folders = ["cogs", "misc"]

    for folder in folders:
        if not os.path.isdir(folder):
            continue

        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            for file in files:
                if not file.endswith(".py") or file in SKIP_FILES or file.startswith("_"):
                    continue

                module = os.path.join(root, file).replace(os.sep, ".")[:-3]

                try:
                    await bot.load_extension(module)
                    loaded += 1
                except Exception:
                    pass


# -----------------------------
# Ready event
# -----------------------------
@bot.event
async def on_ready():
    if not hasattr(bot, "start_time"):
        bot.start_time = discord.utils.utcnow()

    if not bot.synced:
        try:
            await bot.tree.sync()
            bot.synced = True
        except Exception:
            pass

    try:
        await utils.ensure_connection()
    except Exception:
        pass

    await register_persistent_views()


# -----------------------------
# Main
# -----------------------------
async def main():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL missing")

    for i in range(5):
        try:
            await utils.ensure_connection()
            break
        except Exception:
            await asyncio.sleep(5 * (i + 1))
    else:
        raise RuntimeError("DB connection failed")

    await load_cogs()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN missing")

    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
