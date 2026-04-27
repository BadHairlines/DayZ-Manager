import os
import asyncio
import logging
import importlib
import discord
from discord.ext import commands
from cogs import utils

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s]: %(message)s",
    datefmt="%H:%M:%S",
)

discord.utils.setup_logging(level=logging.INFO)
log = logging.getLogger("dayz-manager")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.synced = False


def resolve_flag_manage_view():
    try:
        mod = importlib.import_module("cogs.ui_views")
        return getattr(mod, "FlagManageView", None)
    except Exception as e:
        log.warning(f"Could not load FlagManageView: {e}")
        return None


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


async def register_persistent_views():
    FlagManageView = resolve_flag_manage_view()
    if not FlagManageView:
        log.warning("Missing FlagManageView.")
        return

    await utils.ensure_connection()

    try:
        async with await _acquire_conn() as conn:
            rows = await conn.fetch(
                "SELECT guild_id, map, channel_id, message_id FROM flag_messages;"
            )
    except Exception as e:
        log.warning(f"Failed loading flag messages: {e}")
        return

    if not rows:
        return

    count = 0

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

            count += 1
            log.info(f"Registered view: {guild.name}/{row['map']}")

        except discord.NotFound:
            log.warning(f"Deleted message in {row['guild_id']}/{row['map']}")
        except Exception as e:
            log.warning(f"View register failed {row['guild_id']}: {e}")

    log.info(f"Persistent views registered: {count}")


SKIP_FILES = {"__init__.py", "utils.py", "faction_utils.py", "ui_views.py"}


async def load_cogs():
    loaded = 0
    folders = ["cogs", "misc"]

    for folder in folders:
        if not os.path.isdir(folder):
            continue

        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "helpers")]

            for file in files:
                if not file.endswith(".py") or file in SKIP_FILES or file.startswith("_"):
                    continue

                module = os.path.join(root, file).replace(os.sep, ".")[:-3]

                try:
                    await bot.load_extension(module)
                    log.info(f"Loaded: {module}")
                    loaded += 1
                except Exception:
                    log.exception(f"Failed: {module}")

    log.info(f"Total cogs loaded: {loaded}")


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} ({bot.user.id})")

    if not hasattr(bot, "start_time"):
        bot.start_time = discord.utils.utcnow()

    if not bot.synced:
        try:
            synced = await bot.tree.sync()
            log.info(f"Synced {len(synced)} slash commands.")
            bot.synced = True
        except Exception as e:
            log.error(f"Slash sync failed: {e}")

    try:
        await utils.ensure_connection()
    except Exception as e:
        log.error(f"DB not connected: {e}")

    await register_persistent_views()
    log.info("Bot ready ✅")


async def main():
    log.info("Starting bot...")

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL missing")

    for i in range(5):
        try:
            await utils.ensure_connection()
            log.info("DB connected")
            break
        except Exception as e:
            wait = 5 * (i + 1)
            log.warning(f"DB fail {i+1}/5: {e}")
            await asyncio.sleep(wait)
    else:
        raise RuntimeError("DB connection failed")

    await load_cogs()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN missing")

    async with bot:
        for i in range(3):
            try:
                await bot.start(token)
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    wait = 30 * (i + 1)
                    log.warning(f"Rate limited, retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Bot stopped")
