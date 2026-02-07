from discord.ext import tasks, commands
import logging
from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table

log = logging.getLogger("dayz-manager")

class FactionCleaner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clean_factions_task.start()

    def cog_unload(self):
        self.clean_factions_task.cancel()

    @tasks.loop(hours=1)  # Runs every hour
    async def clean_factions_task(self):
        log.info("Starting automatic faction cleanup...")
        await utils.ensure_connection()
        await ensure_faction_table()

        for guild in self.bot.guilds:
            try:
                async with utils.safe_acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT faction_name, role_id FROM factions WHERE guild_id=$1",
                        str(guild.id)
                    )

                    to_delete = []
                    for row in rows:
                        role_id = row["role_id"]
                        role = guild.get_role(int(role_id)) if role_id else None
                        if not role:
                            to_delete.append(row["faction_name"])

                    if to_delete:
                        await conn.execute(
                            "DELETE FROM factions WHERE guild_id=$1 AND faction_name=ANY($2::text[])",
                            str(guild.id), to_delete
                        )
                        log.info(f"Deleted factions with missing roles in {guild.name}: {to_delete}")
                    else:
                        log.info(f"No factions to delete in {guild.name}")
            except Exception as e:
                log.error(f"Failed to clean factions in {guild.name}: {e}", exc_info=True)

    @clean_factions_task.before_loop
    async def before_clean(self):
        await self.bot.wait_until_ready()
