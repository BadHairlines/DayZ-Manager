from discord.ext import tasks, commands
import logging
from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table

log = logging.getLogger("dayz-manager")


class FactionCleaner(commands.Cog):
    """Automatically cleans up factions and syncs members with Discord roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clean_factions_task.start()

    def cog_unload(self):
        self.clean_factions_task.cancel()

    @tasks.loop(hours=6)
    async def clean_factions_task(self):
        log.info("Starting faction cleanup and sync...")

        try:
            await utils.ensure_connection()
            await ensure_faction_table()
        except Exception as e:
            log.error(f"DB connection failed: {e}", exc_info=True)
            return

        for guild in self.bot.guilds:
            try:
                async with utils.safe_acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT faction_name, role_id, member_ids FROM factions WHERE guild_id=$1",
                        str(guild.id)
                    )

                    factions_to_delete = []
                    factions_to_update = []

                    for row in rows:
                        role_id = row["role_id"]
                        db_member_ids = set(row.get("member_ids") or [])

                        role = guild.get_role(int(role_id)) if role_id else None

                        # Delete faction if role is missing
                        if not role:
                            factions_to_delete.append(row["faction_name"])
                            continue

                        # Sync members from Discord role
                        actual_member_ids = set(str(m.id) for m in role.members)

                        updated_members = db_member_ids & actual_member_ids
                        updated_members |= actual_member_ids

                        if updated_members != db_member_ids:
                            factions_to_update.append(
                                (row["faction_name"], list(updated_members))
                            )

                    # Delete invalid factions
                    if factions_to_delete:
                        await conn.execute(
                            "DELETE FROM factions WHERE guild_id=$1 AND faction_name=ANY($2::text[])",
                            str(guild.id), factions_to_delete
                        )
                        log.info(f"Deleted factions in {guild.name}: {factions_to_delete}")

                    # Update member sync
                    for faction_name, updated_members in factions_to_update:
                        await conn.execute(
                            "UPDATE factions SET member_ids=$1 WHERE guild_id=$2 AND faction_name=$3",
                            updated_members, str(guild.id), faction_name
                        )
                        log.info(
                            f"Synced {len(updated_members)} members for {faction_name} in {guild.name}"
                        )

            except Exception as e:
                log.error(f"Cleanup failed in {guild.name}: {e}", exc_info=True)

        log.info("Faction cleanup completed.")

    @clean_factions_task.before_loop
    async def before_clean(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(FactionCleaner(bot))
