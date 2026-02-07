from discord.ext import tasks, commands
import logging
from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table

log = logging.getLogger("dayz-manager")


class FactionCleaner(commands.Cog):
    """Automatically cleans up factions: deletes factions with missing roles
    and removes members who no longer have the faction role.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.clean_factions_task.start()

    def cog_unload(self):
        self.clean_factions_task.cancel()

    @tasks.loop(hours=1)  # Runs every hour
    async def clean_factions_task(self):
        log.info("Starting automatic faction cleanup...")
        try:
            await utils.ensure_connection()
            await ensure_faction_table()
        except Exception as e:
            log.error(f"Failed to connect to the database: {e}", exc_info=True)
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
                        member_ids = row.get("member_ids") or []

                        role = guild.get_role(int(role_id)) if role_id else None

                        # Delete the entire faction if role no longer exists
                        if not role:
                            factions_to_delete.append(row["faction_name"])
                            continue

                        # Remove members who no longer have the role
                        updated_members = []
                        for mid in member_ids:
                            try:
                                member = guild.get_member(int(mid))
                                if member and role in member.roles:
                                    updated_members.append(mid)
                            except Exception:
                                continue  # skip invalid IDs

                        if set(updated_members) != set(member_ids):
                            factions_to_update.append(
                                (row["faction_name"], updated_members)
                            )

                    # Delete factions with missing roles
                    if factions_to_delete:
                        await conn.execute(
                            "DELETE FROM factions WHERE guild_id=$1 AND faction_name=ANY($2::text[])",
                            str(guild.id), factions_to_delete
                        )
                        log.info(f"Deleted factions with missing roles in {guild.name}: {factions_to_delete}")

                    # Update factions with removed members
                    for faction_name, updated_members in factions_to_update:
                        await conn.execute(
                            "UPDATE factions SET member_ids=$1 WHERE guild_id=$2 AND faction_name=$3",
                            updated_members, str(guild.id), faction_name
                        )
                        removed_count = len(member_ids) - len(updated_members)
                        log.info(f"Removed {removed_count} member(s) from {faction_name} in {guild.name}")

            except Exception as e:
                log.error(f"Failed to clean factions in {guild.name}: {e}", exc_info=True)

    @clean_factions_task.before_loop
    async def before_clean(self):
        await self.bot.wait_until_ready()


# ─── SETUP ───────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(FactionCleaner(bot))
