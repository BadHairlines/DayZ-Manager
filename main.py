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
# LOGGING
# =========================================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("dayz-manager")


# =========================================================
# PATHS / EXTENSIONS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
MISC_DIRECTORY = BASE_DIR / "misc"

# Core features stay explicit. Extra utility cogs may live in misc/.
FLAG_COGS = (
    "cogs.setup",
    "cogs.management",
    "cogs.admin",
    "cogs.auto_refresh",
    "cogs.error_handler",
)


def discover_misc_cogs() -> tuple[str, ...]:
    if not MISC_DIRECTORY.is_dir():
        log.info("No misc directory found; skipping misc cogs.")
        return ()

    return tuple(
        f"misc.{path.stem}"
        for path in sorted(MISC_DIRECTORY.glob("*.py"))
        if not path.name.startswith("_")
    )


# =========================================================
# BOT
# =========================================================

class DayZManager(commands.Bot):
    """DayZ Manager application with deterministic startup/shutdown."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = False
        intents.message_content = False

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self.started_at = discord.utils.utcnow()
        self._shutdown_started = False

    async def setup_hook(self) -> None:
        """Initialize dependencies and commands before READY is dispatched."""
        await initialize_database()
        await load_cogs(self)

        synced = await self.tree.sync()
        log.info("Slash commands synced | count=%d", len(synced))
        for command in synced:
            log.info("Registered command: /%s", command.name)

    async def close(self) -> None:
        if self._shutdown_started:
            return

        self._shutdown_started = True
        log.info("Shutting down DayZ Manager...")

        try:
            await utils.close_db()
            log.info("Database pool closed.")
        except Exception:
            log.exception("Error while closing database pool.")

        await super().close()


bot = DayZManager()


# =========================================================
# STARTUP HELPERS
# =========================================================

async def load_cogs(client: commands.Bot) -> None:
    misc_cogs = discover_misc_cogs()
    extensions = [*(('Core', ext) for ext in FLAG_COGS), *(('Misc', ext) for ext in misc_cogs)]

    log.info(
        "Loading extensions | core=%d misc=%d",
        len(FLAG_COGS),
        len(misc_cogs),
    )

    failures: list[str] = []
    for cog_type, extension in extensions:
        try:
            await client.load_extension(extension)
            log.info("Loaded %s Cog: %s", cog_type, extension)
        except Exception:
            failures.append(extension)
            log.exception("Failed to load %s Cog: %s", cog_type, extension)

    if failures:
        raise RuntimeError(f"Failed to load cog(s): {', '.join(failures)}")


async def initialize_database() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            await utils.ensure_connection()
            log.info("Database connected and migrations complete.")
            return
        except Exception as exc:
            last_error = exc
            log.warning("Database attempt %d/5 failed: %s", attempt, exc)
            if attempt < 5:
                await asyncio.sleep(3)

    raise RuntimeError("Unable to connect to database after 5 attempts.") from last_error


# =========================================================
# EVENTS
# =========================================================

@bot.event
async def on_ready() -> None:
    log.info(
        "Ready as %s (%s) | guilds=%d | latency=%.0fms",
        bot.user,
        bot.user.id if bot.user else "unknown",
        len(bot.guilds),
        bot.latency * 1000,
    )


@bot.event
async def on_error(event: str, *args, **kwargs) -> None:
    log.exception("Unhandled Discord event error: %s", event)


# =========================================================
# SHUTDOWN / ENTRYPOINT
# =========================================================

def install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))
        except (NotImplementedError, RuntimeError):
            pass


async def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")

    install_signal_handlers(asyncio.get_running_loop())
    log.info("Starting DayZ Manager...")

    try:
        await bot.start(token)
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
