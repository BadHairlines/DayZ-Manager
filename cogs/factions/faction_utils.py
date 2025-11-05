# cogs/helpers/faction_utils.py
import discord
import logging
from cogs import utils

log = logging.getLogger("dayz-manager")


async def ensure_faction_table(debug: bool = True):
    """Ensure factions table exists and has required columns. Safe to call multiple times."""
    if utils.db_pool is None:
        log.warning("⚠️ Database pool not initialized — skipping faction table creation.")
        return

    async with utils.safe_acquire() as conn:
        # --- Create main factions table ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS factions (
                id BIGSERIAL PRIMARY KEY,
                guild_id TEXT NOT NULL,
                map TEXT NOT NULL,
                faction_name TEXT NOT NULL,
                role_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                leader_id TEXT NOT NULL,
                member_ids TEXT[],
                color TEXT,
                claimed_flag TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (guild_id, faction_name)
            );
        """)

        # --- Add columns if missing ---
        await conn.execute("""
            ALTER TABLE factions ADD COLUMN IF NOT EXISTS claimed_flag TEXT;
        """)

        # --- Create indexes for performance ---
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_factions_guild_map
            ON factions (guild_id, map);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_factions_name
            ON factions (LOWER(faction_name));
        """)

        # --- Normalize map keys ---
        try:
            await conn.execute("""
                UPDATE factions
                SET map = LOWER(map)
                WHERE map != LOWER(map);
            """)
            if debug:
                log.info("🧩 Normalized existing faction map entries to lowercase.")
        except Exception as e:
            log.warning(f"⚠️ Could not normalize faction map names: {e}")

    if debug:
        log.info("✅ Verified factions table exists and columns are up to date.")


def make_embed(title: str, desc: str, color: int = 0x2ECC71) -> discord.Embed:
    """Create a consistent DayZ Manager faction embed."""
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_author(name="🎭 Faction Manager")
    embed.set_footer(
        text="DayZ Manager • Faction System",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    embed.timestamp = discord.utils.utcnow()
    return embed


def make_log_embed(action: str, details: str, user: discord.Member, color: int = 0xF1C40F) -> discord.Embed:
    """Create a standardized embed for faction-related logs."""
    embed = discord.Embed(
        title=f"🪵 {action}",
        description=details,
        color=color
    )
    embed.set_author(name=f"Action by {user.display_name}", icon_url=user.display_avatar.url)
    embed.set_footer(
        text="Faction Logs • DayZ Manager",
        icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
    )
    embed.timestamp = discord.utils.utcnow()
    return embed
