import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils  # ✅ Use full utils module for shared DB pool
from .faction_utils import ensure_faction_table, make_embed


class FactionDelete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================
    # 🗑️ /delete-faction
    # ============================================
    @app_commands.command(name="delete-faction", description="Delete a faction and remove it from the database.")
    async def delete_faction(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        # 🔒 Permission check
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admin only!", ephemeral=True)

        # 🧩 Ensure DB is ready and table exists
        if utils.db_pool is None:
            raise RuntimeError("❌ Database not initialized yet — please restart the bot.")
        await ensure_faction_table()

        guild = interaction.guild

        # 🔍 Find faction
        async with utils.db_pool.acquire() as conn:
            faction = await conn.fetchrow(
                "SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2",
                str(guild.id), name
            )

        if not faction:
            return await interaction.followup.send(f"❌ Faction `{name}` not found.", ephemeral=True)

        # 💬 Announce & delete faction channel
        if (channel := guild.get_channel(int(faction["channel_id"]))):
            try:
                farewell_embed = make_embed(
                    "💀 Faction Disbanded",
                    f"**{name}** has been officially disbanded. 🕊️"
                )
                await channel.send(embed=farewell_embed)
                await channel.delete(reason="Faction disbanded")
            except Exception as e:
                print(f"⚠️ Failed to delete faction channel: {e}")

        # 🎭 Delete role
        if (role := guild.get_role(int(faction["role_id"]))):
            try:
                await role.delete(reason="Faction disbanded")
            except Exception as e:
                print(f"⚠️ Failed to delete faction role: {e}")

        # 🗃️ Remove from database
        async with utils.db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM factions WHERE guild_id=$1 AND faction_name=$2",
                str(guild.id), name
            )

        # ✅ Confirmation to admin
        confirm_embed = make_embed(
            "✅ Faction Deleted",
            f"Faction **{name}** has been completely removed.",
            color=0xE74C3C
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionDelete(bot))
