import os
import asyncio
import signal
import discord
import aiohttp
from discord.ext import commands

from cogs import utils
from cogs.ui_views import FlagManageView


# -----------------------------
# INTENTS
# -----------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True


# -----------------------------
# BOT CLASS (FIXED: adds session)
# -----------------------------
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.session = None
        self.synced = False
        self._fully_ready = False

    async def setup_hook(self):
        # ✅ THIS FIXES YOUR ERROR
        self.session = aiohttp.ClientSession()

        await load_cogs()
        print("[COGS] Loaded via setup_hook")

    async def close(self):
        print("[SHUTDOWN] Closing bot...")

        if self.session:
            await self.session.close()

        await cleanup_db()
        await super().close()


bot = MyBot()


# -----------------------------
# DATABASE INIT
# -----------------------------
async def init_db():
    await utils.ensure_connection()
    print("[DB] Connected")


async def cleanup_db():
    try:
        if hasattr(utils, "close_connection"):
            await utils.close_connection()
        print("[DB] Disconnected")
    except Exception as e:
        print(f"[DB CLEANUP ERROR] {e}")


# -----------------------------
# COG LOADING
# -----------------------------
SKIP_FILES = {"__init__.py", "utils.py", "ui_views.py"}
COG_FOLDERS = ["cogs", "misc"]


async def load_cogs():
    loaded = 0

    for folder in COG_FOLDERS:
        if not os.path.isdir(folder):
            continue

        for root, _, files in os.walk(folder):
            for file in files:
                if (
                    file in SKIP_FILES
                    or not file.endswith(".py")
                    or file.startswith("_")
                ):
                    continue

                module = (
                    os.path.splitext(
                        os.path.relpath(os.path.join(root, file), start=".")
                    )[0]
                    .replace(os.sep, ".")
                )

                try:
                    await bot.load_extension(module)
                    loaded += 1
                except Exception as e:
                    print(f"[COG ERROR] {module}: {e}")

    print(f"[COGS] Loaded {loaded}")


# -----------------------------
# READY EVENT
# -----------------------------
@bot.event
async def on_ready():
    if bot._fully_ready:
        return

    bot._fully_ready = True

    # Sync slash commands once
    if not bot.synced:
        try:
            await bot.tree.sync()
            bot.synced = True
            print("[SYNC] Slash commands synced")
        except Exception as e:
            print(f"[SYNC ERROR] {e}")

    # Persistent views
    try:
        if not hasattr(utils, "MAP_DATA") or not utils.MAP_DATA:
            print("[VIEWS] Warning: MAP_DATA missing or empty")
        else:
            for map_key in utils.MAP_DATA.keys():
                bot.add_view(FlagManageView(None, map_key, bot))

            print("[VIEWS] Persistent views registered")

    except Exception as e:
        print(f"[VIEWS ERROR] {e}")

    print(f"[READY] Logged in as {bot.user}")


# -----------------------------
# ERROR HANDLING
# -----------------------------
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"[ERROR] Unhandled exception in {event}: {args}")


# -----------------------------
# STARTUP FLOW
# -----------------------------
async def startup():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL missing")

    if not os.getenv("DISCORD_TOKEN"):
        raise RuntimeError("DISCORD_TOKEN missing")

    for attempt in range(5):
        try:
            await init_db()
            break
        except Exception as e:
            print(f"[DB RETRY {attempt + 1}] {e}")
            await asyncio.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError("DB connection failed after retries")


# -----------------------------
# SHUTDOWN
# -----------------------------
async def shutdown():
    print("[SHUTDOWN] Cleaning up...")
    await cleanup_db()
    await bot.close()


def setup_signal_handlers(loop):
    def handler():
        print("[SHUTDOWN] Signal received")
        loop.create_task(shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: handler())


# -----------------------------
# MAIN
# -----------------------------
async def main():
    await startup()

    token = os.environ["DISCORD_TOKEN"]

    loop = asyncio.get_running_loop()
    setup_signal_handlers(loop)

    async with bot:
        await bot.start(token)


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())
