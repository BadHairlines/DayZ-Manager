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
# DATABASE INIT
# -----------------------------
async def init_db():
    await utils.ensure_connection()
    print("[DB] Connected")


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
                if file in SKIP_FILES or not file.endswith(".py") or file.startswith("_"):
                    continue

                module = os.path.join(root, file).replace(os.sep, ".")[:-3]

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
    if not bot.synced:
        try:
            await bot.tree.sync()
            bot.synced = True
            print("[SYNC] Slash commands synced")
        except Exception as e:
            print(f"[SYNC ERROR] {e}")

    print(f"[READY] Logged in as {bot.user}")


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

    await load_cogs()


# -----------------------------
# MAIN
# -----------------------------
async def main():
    await startup()

    token = os.getenv("DISCORD_TOKEN")

    async with bot:
        await bot.start(token)


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())
