import discord
from discord import app_commands
from discord.ext import commands
import logging
from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table, make_embed

log = logging.getLogger("dayz-manager")


class FactionDelete(commands.Cog):
    """Handles faction deletion, cleanup, and flag release."""

    def __init__(self, bot):
        self.bot = bot
        self._locks = {}

    @app_commands.command(
        name="delete-faction",
        description="Delete a faction and remove it from the database."
    )
    async def delete_faction(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("🚫 Admin only!", ephemeral=True)

        await utils.ensure_connection()
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)

        lock = self._locks.setdefault(guild_id, discord.utils.MISSING)
        if lock is discord.utils.MISSING:
            import asyncio
            lock = asyncio.Lock()
            self._locks[guild_id] = lock

        async with lock:
            try:
                async with utils.safe_acquire() as conn:
                    faction_rec = await conn.fetchrow(
                        "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                        guild_id, name
                    )

                if not faction_rec:
                    return await interaction.followup.send(
                        f"❌ Faction `{name}` not found.",
                        ephemeral=True
                    )

                faction = dict(faction_rec)
                map_key = (faction.get("map") or "").lower()
                claimed_flag = faction.get("claimed_flag")

                # Release flag if needed
                if claimed_flag:
                    try:
                        await utils.release_flag(guild_id, map_key, claimed_flag)

                        async with utils.safe_acquire() as conn:
                            row = await conn.fetchrow(
                                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                                guild_id, map_key
                            )

                        if row:
                            ch = guild.get_channel(int(row["channel_id"]))
                            if ch:
                                try:
                                    msg = await ch.fetch_message(int(row["message_id"]))
                                    embed = await utils.create_flag_embed(guild_id, map_key)
                                    await msg.edit(embed=embed)
                                except (discord.NotFound, discord.Forbidden):
                                    pass

                    except Exception as e:
                        log.error(f"⚠️ Could not release flag {claimed_flag}: {e}", exc_info=True)

                # Delete channel
                channel_id = faction.get("channel_id")
                if channel_id:
                    channel = guild.get_channel(int(channel_id))
                    if channel:
                        try:
                            await channel.delete(reason="Faction disbanded")
                        except discord.Forbidden:
                            log.warning(f"Missing permission to delete channel in {guild.name}.")
                        except Exception as e:
                            log.error(f"Failed deleting channel: {e}", exc_info=True)

                # Delete role
                role_id = faction.get("role_id")
                if role_id:
                    role = guild.get_role(int(role_id))
                    if role:
                        try:
                            await role.delete(reason="Faction disbanded")
                        except discord.Forbidden:
                            log.warning(f"Missing permission to delete role in {guild.name}.")
                        except Exception as e:
                            log.error(f"Failed deleting role: {e}", exc_info=True)

                # Remove DB entry
                async with utils.safe_acquire() as conn:
                    await conn.execute(
                        "DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2",
                        guild_id, name
                    )

                confirm_embed = make_embed(
                    "✅ Faction Deleted",
                    f"Faction **{name}** has been removed successfully.\n\n"
                    f"🏳️ Flag: `{claimed_flag or 'None'}` freed."
                )

                await interaction.followup.send(embed=confirm_embed, ephemeral=True)
                log.info(f"Deleted faction '{name}' in {guild.name} ({map_key}).")

            except Exception as e:
                log.error(f"Faction deletion failed in {guild.name}: {e}", exc_info=True)
                await interaction.followup.send(
                    f"❌ Deletion failed:\n```{e}```",
                    ephemeral=True
                )


async def setup(bot):
    await bot.add_cog(FactionDelete(bot))
