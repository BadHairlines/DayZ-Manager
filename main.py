import os
import asyncio
import discord
from discord.ext import commands
from cogs import utils

# -----------------------------
# BOT SETUP
# -----------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False


# -----------------------------
# DATABASE CONNECTION HELPER
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
# COG LOADER
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
                except Exception as e:
                    print(f"[COG LOAD ERROR] {module}: {e}")

    print(f"[COGS LOADED] {loaded}")


# -----------------------------
# READY EVENT
# -----------------------------
@bot.event
async def on_ready():
    if not hasattr(bot, "start_time"):
        bot.start_time = discord.utils.utcnow()

    if not bot.synced:
        try:
            await bot.tree.sync()
            bot.synced = True
            print("[SYNC] Slash commands synced")
        except Exception as e:
            print(f"[SYNC ERROR] {e}")

    try:
        await utils.ensure_connection()
        print("[DB] Connected")
    except Exception as e:
        print(f"[DB ERROR] {e}")

    print(f"[READY] Logged in as {bot.user}")


# -----------------------------
# MAIN ENTRY POINT
# -----------------------------
async def main():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL missing")

    # Retry DB connection
    for i in range(5):
        try:
            await utils.ensure_connection()
            break
        except Exception as e:
            print(f"[DB RETRY {i+1}] {e}")
            await asyncio.sleep(5 * (i + 1))
    else:
        raise RuntimeError("DB connection failed")

    await load_cogs()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN missing")

    try:
        async with bot:
            await bot.start(token)
    finally:
        # Clean shutdown
        await utils.close_db()
        print("[SHUTDOWN] Database closed")


# -----------------------------
# START BOT
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())
