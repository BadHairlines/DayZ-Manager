from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

import discord
from discord.ext import commands

from cogs import utils


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

COG_DIRECTORIES = (
    BASE_DIR / "cogs",
    BASE_DIR / "misc",
)

SKIP_FILES = {
    "__init__.py",
    "utils.py",
    "ui_views.py",
}


# =========================================================
# BOT SETUP
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)

# Runtime state
bot.synced = False
bot._fully_ready = False
bot._shutdown_started = False


# =========================================================
# DATABASE
# =========================================================

async def init_db() -> None:
    """Initialize the database connection."""

    await utils.ensure_connection()

    print("[DB] Connected")


async def cleanup_db() -> None:
    """Close the database connection safely."""

    try:

        await utils.close_db()

        print("[DB] Disconnected")

    except Exception as exc:

        print(
            f"[DB CLEANUP ERROR] "
            f"{type(exc).__name__}: {exc}"
        )


# =========================================================
# COG DISCOVERY
# =========================================================

def discover_cogs() -> list[str]:
    """
    Discover all cog modules recursively.

    Example:

        misc/reminder.py
            -> misc.reminder

        misc/server/restartinfo.py
            -> misc.server.restartinfo

        cogs/flags/setup.py
            -> cogs.flags.setup
    """

    modules: list[str] = []

    for directory in COG_DIRECTORIES:

        if not directory.is_dir():
            continue

        for file_path in directory.rglob("*.py"):

            if file_path.name in SKIP_FILES:
                continue

            if file_path.name.startswith("_"):
                continue

            relative_path = file_path.relative_to(BASE_DIR)

            module = ".".join(
                relative_path.with_suffix("").parts
            )

            modules.append(module)

    return sorted(modules)


# =========================================================
# COG LOADING
# =========================================================

async def load_cogs() -> None:
    """Load every discovered Discord.py extension."""

    modules = discover_cogs()

    if not modules:

        print("[COGS] No cog files found.")

        return

    loaded = 0
    failed = 0

    print(
        f"[COGS] Found {len(modules)} extension(s)"
    )

    for module in modules:

        try:

            await bot.load_extension(module)

            loaded += 1

            print(
                f"[COG] Loaded: {module}"
            )

        except Exception as exc:

            failed += 1

            print(
                f"[COG ERROR] {module}: "
                f"{type(exc).__name__}: {exc}"
            )

    print(
        f"[COGS] Loaded: {loaded} | "
        f"Failed: {failed}"
    )

    if failed:

        print(
            "[COGS] One or more extensions "
            "failed to load."
        )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready() -> None:
    """
    Discord ready event.

    Persistent flag views are restored by the
    AutoRefresh cog rather than being hard-coded here.
    """

    if bot._fully_ready:

        print(
            f"[READY] Reconnected as {bot.user}"
        )

        return

    bot._fully_ready = True

    # -----------------------------------------------------
    # SLASH COMMAND SYNC
    # -----------------------------------------------------

    if not bot.synced:

        try:

            await bot.tree.sync()

            bot.synced = True

            print(
                "[SYNC] Slash commands synced"
            )

        except Exception as exc:

            print(
                f"[SYNC ERROR] "
                f"{type(exc).__name__}: {exc}"
            )

    # -----------------------------------------------------
    # READY
    # -----------------------------------------------------

    print(
        f"[READY] Logged in as "
        f"{bot.user} "
        f"(ID: {bot.user.id})"
    )

    print(
        f"[READY] Connected to "
        f"{len(bot.guilds)} guild(s)"
    )


# =========================================================
# GLOBAL ERROR HANDLING
# =========================================================

@bot.event
async def on_error(
    event: str,
    *args,
    **kwargs,
) -> None:

    print(
        f"[ERROR] Unhandled exception "
        f"in event '{event}'"
    )


# =========================================================
# STARTUP
# =========================================================

async def startup() -> None:
    """Validate environment and start bot services."""

    print(
        "[STARTUP] Starting DayZ Manager..."
    )

    # -----------------------------------------------------
    # ENVIRONMENT
    # -----------------------------------------------------

    database_url = os.getenv(
        "DATABASE_URL"
    )

    discord_token = os.getenv(
        "DISCORD_TOKEN"
    )

    if not database_url:

        raise RuntimeError(
            "DATABASE_URL environment variable "
            "is missing."
        )

    if not discord_token:

        raise RuntimeError(
            "DISCORD_TOKEN environment variable "
            "is missing."
        )

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    for attempt in range(1, 6):

        try:

            await init_db()

            break

        except Exception as exc:

            print(
                f"[DB RETRY {attempt}/5] "
                f"{type(exc).__name__}: {exc}"
            )

            if attempt >= 5:

                raise RuntimeError(
                    "Database connection failed "
                    "after 5 attempts."
                ) from exc

            await asyncio.sleep(
                3 * attempt
            )

    # -----------------------------------------------------
    # COGS
    # -----------------------------------------------------

    await load_cogs()

    print(
        "[STARTUP] Startup complete."
    )


# =========================================================
# SHUTDOWN
# =========================================================

async def shutdown() -> None:
    """Safely shut down the bot and database."""

    if bot._shutdown_started:

        return

    bot._shutdown_started = True

    print(
        "[SHUTDOWN] Cleaning up..."
    )

    try:

        await cleanup_db()

    finally:

        if not bot.is_closed():

            await bot.close()

    print(
        "[SHUTDOWN] Complete."
    )


# =========================================================
# SIGNAL HANDLERS
# =========================================================

def setup_signal_handlers(
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Register SIGINT/SIGTERM shutdown handlers."""

    def handler() -> None:

        if bot._shutdown_started:

            return

        print(
            "[SHUTDOWN] Signal received"
        )

        asyncio.create_task(
            shutdown()
        )

    for sig in (
        signal.SIGINT,
        signal.SIGTERM,
    ):

        try:

            loop.add_signal_handler(
                sig,
                handler,
            )

        except (
            NotImplementedError,
            RuntimeError,
        ):

            # Windows may not support all asyncio
            # signal handling functionality.
            signal.signal(
                sig,
                lambda *_: handler(),
            )


# =========================================================
# MAIN
# =========================================================

async def main() -> None:

    await startup()

    token = os.environ[
        "DISCORD_TOKEN"
    ]

    loop = asyncio.get_running_loop()

    setup_signal_handlers(
        loop
    )

    try:

        await bot.start(
            token
        )

    finally:

        if not bot._shutdown_started:

            await shutdown()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass
