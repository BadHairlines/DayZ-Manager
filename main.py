from __future__ import annotations

import asyncio
import logging
import os
import signal

import discord
from discord.ext import commands

from cogs import utils


# =========================================================
# LOGGING
# =========================================================

LOG = logging.getLogger("dayz-manager")


def configure_logging() -> None:
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
# FLAG SYSTEM COGS
# =========================================================
#
# IMPORTANT:
# Only these extensions are allowed to load.
#
# This prevents old/unrelated Cogs such as:
#
#     cogs/challenges.py
#     cogs/teleporter.py
#     cogs/vehicle.py
#     cogs/todo.py
#
# from accidentally becoming Discord commands.
#
# =========================================================

FLAG_COGS = (
    "cogs.setup",
    "cogs.management",
    "cogs.auto_refresh",
    "cogs.error_handler",
)


# =========================================================
# DISCORD INTENTS
# =========================================================
#
# The Flag System uses:
#
#     Guild information
#     Roles
#     Interactions / slash commands
#     Buttons
#     Select menus
#
# It does NOT need:
#
#     Members privileged intent
#     Message Content privileged intent
#
# =========================================================

intents = discord.Intents.default()

intents.guilds = True

# PRIVILEGED INTENTS ARE NOT REQUIRED
intents.members = False
intents.message_content = False


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
bot._auto_refresh_done = False


# =========================================================
# LOAD COGS
# =========================================================

async def load_cogs() -> None:
    """
    Load ONLY the approved Flag System Cogs.
    """

    LOG.info(
        "Loading %d Flag System Cog(s)...",
        len(FLAG_COGS),
    )

    loaded = 0
    failed = 0

    for module in FLAG_COGS:

        try:
            await bot.load_extension(module)

            loaded += 1

            LOG.info(
                "Loaded Flag Cog: %s",
                module,
            )

        except Exception:

            failed += 1

            LOG.exception(
                "Failed to load Flag Cog: %s",
                module,
            )

    LOG.info(
        "Flag Cog loading complete | loaded=%d failed=%d",
        loaded,
        failed,
    )

    if failed:
        raise RuntimeError(
            f"{failed} Flag System Cog(s) failed to load."
        )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

async def initialize_database() -> None:
    """
    Initialize the Flag System database connection.
    """

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing."
        )

    for attempt in range(1, 6):

        try:

            await utils.ensure_connection()

            LOG.info(
                "Database connected."
            )

            return

        except Exception:

            LOG.exception(
                "Database connection attempt %d/5 failed.",
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
        2. Connect database
        3. Load approved Flag System Cogs
    """

    token = os.getenv(
        "DISCORD_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN environment variable is missing."
        )

    # -----------------------------------------------------
    # Database
    # -----------------------------------------------------

    await initialize_database()

    # -----------------------------------------------------
    # Flag System Cogs
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
    # Reconnection
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
    # Sync slash commands once
    # -----------------------------------------------------

    if not bot.synced:

        try:

            synced_commands = await bot.tree.sync()

            bot.synced = True

            LOG.info(
                "Slash commands synced | count=%d",
                len(synced_commands),
            )

            for command in synced_commands:

                LOG.info(
                    "Registered command: /%s",
                    command.qualified_name,
                )

        except Exception:

            LOG.exception(
                "Slash command sync failed."
            )

    # -----------------------------------------------------
    # Startup information
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
    Gracefully shut down the bot and database.
    """

    if bot._shutdown_started:
        return

    bot._shutdown_started = True

    LOG.info(
        "Shutdown started."
    )

    # -----------------------------------------------------
    # Close database
    # -----------------------------------------------------

    try:

        await utils.close_db()

    except Exception:

        LOG.exception(
            "Database cleanup failed."
        )

    # -----------------------------------------------------
    # Close Discord
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
                    "Could not install signal handler for %s.",
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
    # Initialize application
    # -----------------------------------------------------

    await initialize()

    # -----------------------------------------------------
    # Install shutdown handlers
    # -----------------------------------------------------

    loop = asyncio.get_running_loop()

    install_signal_handlers(
        loop
    )

    # -----------------------------------------------------
    # Start Discord
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
