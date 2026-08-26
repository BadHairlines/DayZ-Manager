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


# =========================================================
# FILES THAT ARE NOT COGS
# =========================================================
#
# These files contain support code only.
#
# Examples:
#
#   cogs/utils.py
#   cogs/database.py
#   cogs/todo/database.py
#   cogs/todo/views.py
#
# They must remain importable by their respective systems,
# but they must NEVER be loaded as Discord extensions.
#

SKIP_FILES = {
    "__init__.py",
    "utils.py",
    "database.py",
    "views.py",
}


# =========================================================
# DIRECTORIES THAT ARE NOT COGS
# =========================================================

SKIP_DIRECTORIES = {
    "__pycache__",
    "helpers",
    "ui",
}


# =========================================================
# LOGGING
# =========================================================

LOG = logging.getLogger("dayz-manager")


def configure_logging() -> None:
    """
    Configure application-wide logging.
    """

    logging.basicConfig(
        level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ).upper(),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
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


# =========================================================
# INTERNAL BOT STATE
# =========================================================

bot.synced = False
bot._fully_ready = False
bot._shutdown_started = False


# =========================================================
# COG DISCOVERY
# =========================================================

def discover_cogs() -> list[str]:
    """
    Discover actual Discord extension modules.

    Support modules are intentionally ignored.

    Example:

        cogs/todo/todo.py
            -> cogs.todo.todo

        cogs/todo/database.py
            -> ignored

        cogs/todo/views.py
            -> ignored
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

            relative_parts = path.relative_to(
                BASE_DIR
            ).parts

            if any(
                part in SKIP_DIRECTORIES
                for part in relative_parts
            ):
                continue

            # -------------------------------------------------
            # Convert filesystem path to Python module.
            #
            # Example:
            #
            # cogs/flags/flags.py
            #
            # becomes:
            #
            # cogs.flags.flags
            # -------------------------------------------------

            relative = path.relative_to(
                BASE_DIR
            )

            module = ".".join(
                relative.with_suffix("").parts
            )

            modules.add(module)

    return sorted(modules)


# =========================================================
# LOAD COGS
# =========================================================

async def load_cogs() -> None:
    """
    Load every discovered Discord Cog.

    A single failed Cog prevents startup so that a broken
    system cannot silently leave the bot partially loaded.
    """

    modules = discover_cogs()

    if not modules:

        LOG.warning(
            "No Cog files were discovered."
        )

        return

    LOG.info(
        "Discovered %d Cog(s).",
        len(modules),
    )

    loaded = 0
    failed = 0

    for module in modules:

        try:

            await bot.load_extension(
                module
            )

            loaded += 1

            LOG.info(
                "Loaded Cog: %s",
                module,
            )

        except Exception:

            failed += 1

            LOG.exception(
                "Failed to load Cog: %s",
                module,
            )

    LOG.info(
        "Cog loading complete | "
        "loaded=%d failed=%d",
        loaded,
        failed,
    )

    # -----------------------------------------------------
    # Do not allow the bot to start partially broken.
    # -----------------------------------------------------

    if failed:

        raise RuntimeError(
            f"{failed} Cog(s) failed to load."
        )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

async def initialize_database() -> None:
    """
    Initialize the MAIN bot database.

    IMPORTANT:
    The To-Do system has its own database module and
    initializes itself when cogs.todo.todo is loaded.

    This keeps the two systems separate.
    """

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if not database_url:

        raise RuntimeError(
            "DATABASE_URL environment variable is missing."
        )

    # -----------------------------------------------------
    # Main application database.
    #
    # This is NOT the To-Do database.
    # -----------------------------------------------------

    for attempt in range(1, 6):

        try:

            await utils.ensure_connection()

            LOG.info(
                "Main database connected."
            )

            return

        except Exception:

            LOG.exception(
                "Main database connection "
                "attempt %d/5 failed.",
                attempt,
            )

            if attempt == 5:
                raise

            await asyncio.sleep(
                min(
                    3 * attempt,
                    15,
                )
            )


# =========================================================
# INITIALIZATION
# =========================================================

async def initialize() -> None:
    """
    Initialize everything required before Discord starts.

    Order:

        1. Validate environment
        2. Connect main database
        3. Load Cogs

    Individual Cogs are responsible for initializing their
    own separate databases/resources.
    """

    token = os.getenv(
        "DISCORD_TOKEN"
    )

    if not token:

        raise RuntimeError(
            "DISCORD_TOKEN environment variable is missing."
        )

    # -----------------------------------------------------
    # Main database.
    # -----------------------------------------------------

    await initialize_database()

    # -----------------------------------------------------
    # Load all Discord Cogs.
    #
    # The To-Do Cog will initialize:
    #
    #     cogs.todo.database
    #
    # independently during its setup().
    # -----------------------------------------------------

    await load_cogs()


# =========================================================
# DISCORD EVENTS
# =========================================================

@bot.event
async def on_ready() -> None:
    """
    Fired when Discord establishes a connection.

    on_ready can fire multiple times after reconnects.
    """

    # -----------------------------------------------------
    # Reconnection.
    # -----------------------------------------------------

    if bot._fully_ready:

        LOG.info(
            "Reconnected as %s (%s).",
            bot.user,
            (
                bot.user.id
                if bot.user
                else "unknown"
            ),
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

    # -----------------------------------------------------
    # Startup information.
    # -----------------------------------------------------

    LOG.info(
        "Logged in as %s (%s).",
        bot.user,
        (
            bot.user.id
            if bot.user
            else "unknown"
        ),
    )

    LOG.info(
        "Connected to %d guild(s).",
        len(bot.guilds),
    )


# =========================================================
# GLOBAL EVENT ERROR HANDLER
# =========================================================

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
    """
    Gracefully shut down the bot and main database.
    """

    if bot._shutdown_started:
        return

    bot._shutdown_started = True

    LOG.info(
        "Shutdown started."
    )

    # -----------------------------------------------------
    # Close MAIN database.
    #
    # The To-Do database is intentionally separate and
    # should be closed by its own system.
    # -----------------------------------------------------

    try:

        await utils.close_db()

    except Exception:

        LOG.exception(
            "Main database cleanup failed."
        )

    # -----------------------------------------------------
    # Close Discord.
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
    """
    Install graceful SIGINT/SIGTERM handlers.
    """

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

            # -------------------------------------------------
            # Windows fallback.
            # -------------------------------------------------

            try:

                signal.signal(
                    sig,
                    lambda *_: request_shutdown(),
                )

            except (
                ValueError,
                OSError,
            ):

                LOG.debug(
                    "Could not install signal handler "
                    "for %s.",
                    sig,
                )


# =========================================================
# MAIN
# =========================================================

async def main() -> None:

    configure_logging()

    LOG.info(
        "Starting DayZ Manager..."
    )

    # -----------------------------------------------------
    # Initialize application.
    # -----------------------------------------------------

    await initialize()

    # -----------------------------------------------------
    # Install shutdown handlers after the event loop exists.
    # -----------------------------------------------------

    loop = asyncio.get_running_loop()

    install_signal_handlers(
        loop
    )

    # -----------------------------------------------------
    # Start Discord.
    # -----------------------------------------------------

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

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass
