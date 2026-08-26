from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

import discord
from discord.ext import commands

from cogs import utils


# =========================================================
# PATHS / COG DISCOVERY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

COG_DIRECTORIES = (
    BASE_DIR / "cogs",
    BASE_DIR / "misc",
)

# Files that should never be loaded as Discord extensions.
#
# These are support modules, not actual Cogs.
SKIP_FILES = {
    "__init__.py",
    "utils.py",
    "database.py",
    "views.py",
}

# Directories containing support modules rather than actual Cogs.
SKIP_DIRECTORIES = {
    "helpers",
    "ui",
}


# =========================================================
# LOGGING
# =========================================================

LOG = logging.getLogger("dayz-manager")


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# =========================================================
# DISCORD BOT
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

# Internal bot state.
bot.synced = False
bot._fully_ready = False
bot._shutdown_started = False
bot._auto_refresh_done = False


# =========================================================
# COG DISCOVERY
# =========================================================

def discover_cogs() -> list[str]:
    """
    Automatically discover actual Discord Cog extensions.

    Support modules such as:
        cogs/utils.py
        cogs/helpers/*
        cogs/ui/*
        cogs/todo/database.py
        cogs/todo/views.py

    are intentionally ignored.
    """

    modules: set[str] = set()

    for directory in COG_DIRECTORIES:
        if not directory.is_dir():
            continue

        for path in directory.rglob("*.py"):

            # -------------------------------------------------
            # Skip support files.
            # -------------------------------------------------

            if path.name in SKIP_FILES:
                continue

            if path.name.startswith("_"):
                continue

            # -------------------------------------------------
            # Skip support directories.
            # -------------------------------------------------

            relative_parts = path.relative_to(BASE_DIR).parts

            if any(
                directory_name in SKIP_DIRECTORIES
                for directory_name in relative_parts
            ):
                continue

            # -------------------------------------------------
            # Convert filesystem path to Python module path.
            #
            # cogs/flags/setup.py
            #     ->
            # cogs.flags.setup
            #
            # cogs/todo/todo.py
            #     ->
            # cogs.todo.todo
            # -------------------------------------------------

            relative = path.relative_to(BASE_DIR)

            module = ".".join(
                relative.with_suffix("").parts
            )

            modules.add(module)

    return sorted(modules)


# =========================================================
# LOAD COGS
# =========================================================

async def load_cogs() -> None:
    modules = discover_cogs()

    if not modules:
        LOG.warning("No cog files found.")
        return

    loaded = 0
    failed = 0

    LOG.info(
        "Discovered %d cog(s).",
        len(modules),
    )

    for module in modules:
        try:
            await bot.load_extension(module)

            loaded += 1

            LOG.info(
                "Loaded cog: %s",
                module,
            )

        except Exception:
            failed += 1

            LOG.exception(
                "Failed to load cog: %s",
                module,
            )

    LOG.info(
        "Cog loading complete | loaded=%d failed=%d",
        loaded,
        failed,
    )

    if failed:
        raise RuntimeError(
            f"{failed} cog(s) failed to load."
        )


# =========================================================
# INITIALIZATION
# =========================================================

async def initialize() -> None:
    database_url = os.getenv("DATABASE_URL")
    token = os.getenv("DISCORD_TOKEN")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing."
        )

    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN environment variable is missing."
        )

    # -----------------------------------------------------
    # Database connection with retry logic.
    # -----------------------------------------------------

    for attempt in range(1, 6):
        try:
            await utils.ensure_connection()

            LOG.info(
                "Database connected."
            )

            break

        except Exception:
            LOG.exception(
                "Database connection attempt %d/5 failed.",
                attempt,
            )

            if attempt == 5:
                raise

            await asyncio.sleep(
                min(3 * attempt, 15)
            )

    # -----------------------------------------------------
    # Load Discord Cogs.
    # -----------------------------------------------------

    await load_cogs()


# =========================================================
# DISCORD EVENTS
# =========================================================

@bot.event
async def on_ready() -> None:

    # Discord can fire on_ready more than once
    # after reconnects.

    if bot._fully_ready:

        LOG.info(
            "Reconnected as %s (%s).",
            bot.user,
            bot.user.id if bot.user else "unknown",
        )

        return

    bot._fully_ready = True

    # -----------------------------------------------------
    # Sync slash commands once.
    # -----------------------------------------------------

    if not bot.synced:

        try:
            await bot.tree.sync()

            bot.synced = True

            LOG.info(
                "Slash commands synced."
            )

        except Exception:
            LOG.exception(
                "Slash command sync failed."
            )

    LOG.info(
        "Logged in as %s (%s).",
        bot.user,
        bot.user.id if bot.user else "unknown",
    )

    LOG.info(
        "Connected to %d guild(s).",
        len(bot.guilds),
    )


@bot.event
async def on_error(
    event: str,
    *args,
    **kwargs,
) -> None:

    LOG.exception(
        "Unhandled exception in event '%s'.",
        event,
    )


# =========================================================
# SHUTDOWN
# =========================================================

async def shutdown() -> None:

    if bot._shutdown_started:
        return

    bot._shutdown_started = True

    LOG.info(
        "Shutdown started."
    )

    # -----------------------------------------------------
    # Close database.
    # -----------------------------------------------------

    try:
        await utils.close_db()

    except Exception:
        LOG.exception(
            "Database cleanup failed."
        )

    # -----------------------------------------------------
    # Close Discord connection.
    # -----------------------------------------------------

    try:

        if not bot.is_closed():
            await bot.close()

    except Exception:
        LOG.exception(
            "Discord client cleanup failed."
        )

    LOG.info(
        "Shutdown complete."
    )


# =========================================================
# SIGNAL HANDLERS
# =========================================================

def install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
) -> None:

    def request_shutdown() -> None:

        if bot._shutdown_started:
            return

        LOG.info(
            "Shutdown signal received."
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
                request_shutdown,
            )

        except (
            NotImplementedError,
            RuntimeError,
        ):

            try:

                signal.signal(
                    sig,
                    lambda *_: request_shutdown(),
                )

            except (
                ValueError,
                OSError,
            ):
                pass


# =========================================================
# MAIN
# =========================================================

async def main() -> None:

    configure_logging()

    LOG.info(
        "Starting DayZ Manager..."
    )

    await initialize()

    loop = asyncio.get_running_loop()

    install_signal_handlers(loop)

    try:

        await bot.start(
            os.environ["DISCORD_TOKEN"]
        )

    finally:

        await shutdown()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:
        pass
