import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils
from .faction_utils import ensure_faction_table, make_embed


class FactionDelete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="delete-faction",
        description="Delete a faction and remove it from the database."
    )
    async def delete_faction(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admin only!", ephemeral=True)

        if utils.db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild
        guild_id = str(guild.id)

        async with utils.db_pool.acquire() as conn:
            faction_rec = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                guild_id, name
            )

        if not faction_rec:
            return await interaction.followup.send(f"❌ Faction `{name}` not found.", ephemeral=True)

        faction = dict(faction_rec)
        map_key = (faction.get("map") or "").lower()
        claimed_flag = faction.get("claimed_flag") or None

        if claimed_flag:
            try:
                await utils.release_flag(guild_id, map_key, claimed_flag)
                await utils.log_action(
                    guild,
                    map_key,
                    title="Flag Released (Faction Deleted)",
                    description=f"🏳️ Flag **{claimed_flag}** was freed after `{name}` disbanded."
                )
                try:
                    embed = await utils.create_flag_embed(guild_id, map_key)
                    async with utils.db_pool.acquire() as conn:
                        row = await conn.fetchrow(
                            "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                            guild_id, map_key
                        )
                    if row:
                        ch = guild.get_channel(int(row["channel_id"]))
                        if ch:
                            try:
                                msg = await ch.fetch_message(int(row["message_id"]))
                                await msg.edit(embed=embed)
                            except discord.NotFound:
                                pass
                except Exception as e:
                    print(f"⚠️ Failed to refresh flag display after faction deletion: {e}")
            except Exception as e:
                print(f"⚠️ Could not release flag {claimed_flag}: {e}")

        channel_id_raw = faction.get("channel_id")
        try:
            channel_id = int(channel_id_raw) if channel_id_raw is not None else None
        except (TypeError, ValueError):
            channel_id = None

        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    farewell_embed = make_embed(
                        "💀 Faction Disbanded",
                        f"**{name}** has been officially disbanded. 🕊️"
                    )
                    await channel.send(embed=farewell_embed)
                    await channel.delete(reason="Faction disbanded")
                except Exception as e:
                    print(f"⚠️ Failed to delete faction channel: {e}")

        role_id_raw = faction.get("role_id")
        try:
            role_id = int(role_id_raw) if role_id_raw is not None else None
        except (TypeError, ValueError):
            role_id = None

        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await role.delete(reason="Faction disbanded")
                except Exception as e:
                    print(f"⚠️ Failed to delete faction role: {e}")

        async with utils.db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2",
                guild_id, name
            )

        await utils.log_faction_action(
            guild,
            action="Faction Deleted",
            faction_name=name,
            user=interaction.user,
            details=f"Faction `{name}` was deleted by {interaction.user.mention}.",
            map_key=map_key,
        )

        confirm_embed = make_embed(
            "✅ Faction Deleted",
            f"Faction **{name}** has been completely removed and its flag freed.",
            color=0xE74C3C
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionDelete(bot))
