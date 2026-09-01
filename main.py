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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

log = logging.getLogger("dayz-manager")


# =========================================================
# FLAG SYSTEM COGS
# =========================================================

# IMPORTANT:
# Keep this list explicit.
# Do NOT dynamically load every .py file in /cogs.
#
# The bot is ONLY the Flag System.
FLAG_COGS = (
    "cogs.setup",
    "cogs.management",
    "cogs.auto_refresh",
    "cogs.error_handler",
)


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()

# Required for guild/server functionality.
intents.guilds = True

# NOT required by the Flag System.
# These are privileged intents and should remain disabled.
intents.members = False
intents.message_content = False

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)


# =========================================================
# STATE
# =========================================================

bot.synced = False
bot._fully_ready = False
bot._shutdown_started = False


# =========================================================
# LOAD COGS
# =========================================================

async def load_cogs() -> None:
    """Load only the explicitly approved Flag System cogs."""

    log.info("Loading %d Flag System Cog(s)...", len(FLAG_COGS))

    loaded = 0
    failed = 0

    for extension in FLAG_COGS:
        try:
            await bot.load_extension(extension)
            loaded += 1
            log.info("Loaded Flag Cog: %s", extension)

        except Exception:
            failed += 1
            log.exception("Failed to load Flag Cog: %s", extension)

    log.info(
        "Flag Cog loading complete | loaded=%d failed=%d",
        loaded,
        failed,
    )

    if failed:
        raise RuntimeError(
            f"{failed} Flag System Cog(s) failed to load."
        )


# =========================================================
# DATABASE
# =========================================================

async def initialize_database() -> None:
    """Initialize the database connection and schema."""

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    last_error: Exception | None = None

    for attempt in range(1, 6):
        try:
            await utils.ensure_connection()
            log.info("Database connected.")
            return

        except Exception as exc:
            last_error = exc

            log.warning(
                "Database connection attempt %d/5 failed: %s",
                attempt,
                exc,
            )

            if attempt < 5:
                await asyncio.sleep(3)

    raise RuntimeError(
        "Unable to connect to the database after 5 attempts."
    ) from last_error


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():
    """Called when Discord connection is ready."""

    if bot._fully_ready:
        return

    log.info(
        "Connected to Discord as %s (%s)",
        bot.user,
        bot.user.id if bot.user else "unknown",
    )

    log.info("Connected to %d guild(s).", len(bot.guilds))

    if not bot.synced:
        try:
            commands_synced = await bot.tree.sync()

            bot.synced = True

            log.info(
                "Slash commands synced successfully | count=%d",
                len(commands_synced),
            )

            for command in commands_synced:
                log.info("Registered command: /%s", command.name)

        except Exception:
            log.exception("Failed to sync slash commands.")
            raise

    bot._fully_ready = True

    log.info("DayZ Manager is fully ready.")


# =========================================================
# GLOBAL ERROR HANDLER
# =========================================================

@bot.event
async def on_error(event, *args, **kwargs):
    log.exception(
        "Unhandled Discord event error: %s",
        event,
    )


# =========================================================
# SHUTDOWN
# =========================================================

async def shutdown() -> None:
    """Gracefully shut down the bot and database."""

    if bot._shutdown_started:
        return

    bot._shutdown_started = True

    log.info("Shutting down DayZ Manager...")

    try:
        await utils.close_db()
        log.info("Database connection closed.")
    except Exception:
        log.exception("Error while closing database.")

    try:
        await bot.close()
        log.info("Discord connection closed.")
    except Exception:
        log.exception("Error while closing Discord connection.")


# =========================================================
# SIGNAL HANDLERS
# =========================================================

def install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Install graceful shutdown handlers where supported."""

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig,
                lambda sig=sig: asyncio.create_task(
                    shutdown()
                ),
            )
        except (NotImplementedError, RuntimeError):
            # Windows may not support add_signal_handler.
            pass


# =========================================================
# MAIN
# =========================================================

async def initialize() -> None:
    """Initialize everything required before Discord login."""

    token = os.getenv("DISCORD_TOKEN")

    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN environment variable is not set."
        )

    log.info("Starting DayZ Manager...")

    await initialize_database()

    await load_cogs()

    await bot.start(token)


async def main() -> None:
    loop = asyncio.get_running_loop()

    install_signal_handlers(loop)

    try:
        await initialize()

    except KeyboardInterrupt:
        log.info("Keyboard interrupt received.")

    except Exception:
        log.exception("Fatal startup error.")

    finally:
        await shutdown()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
