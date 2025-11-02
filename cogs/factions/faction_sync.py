import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils  # ✅ shared DB + logging
from .faction_utils import make_embed, ensure_faction_table


class FactionSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================
    # 🔄 /sync-factions
    # ============================================
    @app_commands.command(name="sync-factions", description="Synchronize all faction and flag ownership data.")
    @app_commands.describe(confirm="Confirm sync operation (required)")
    async def sync_factions(self, interaction: discord.Interaction, confirm: bool):
        """Syncs existing factions with current flag ownership (no auto-create)."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        # 🔒 Permission check
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admins only.", ephemeral=True)

        if not confirm:
            return await interaction.followup.send("⚠️ Sync canceled — confirmation not given.", ephemeral=True)

        guild = interaction.guild

        # 🧩 Ensure database + table ready
        if utils.db_pool is None:
            return await interaction.followup.send("❌ Database not initialized. Restart the bot.", ephemeral=True)
        await ensure_faction_table()

        updated = 0
        skipped = 0
        total_factions = 0

        async with utils.db_pool.acquire() as conn:
            factions = await conn.fetch("SELECT * FROM factions WHERE guild_id=$1", str(guild.id))
            total_factions = len(factions)

            # Fetch all flag data for the guild
            all_flags = await conn.fetch("SELECT map, flag, role_id FROM flags WHERE guild_id=$1", str(guild.id))
            role_to_flag = {r["role_id"]: (r["map"], r["flag"]) for r in all_flags if r["role_id"]}

            # 🔁 Iterate factions and update their flag info if needed
            for faction in factions:
                faction_role_id = faction["role_id"]
                if faction_role_id in role_to_flag:
                    flag_map, flag_name = role_to_flag[faction_role_id]

                    # Optional future-proofing: if you add a "claimed_flag" column later, update it here
                    # await conn.execute(
                    #     "UPDATE factions SET claimed_flag=$1 WHERE id=$2",
                    #     flag_name, faction["id"]
                    # )

                    updated += 1

                    await utils.log_faction_action(
                        guild,
                        action="Faction Synced",
                        faction_name=faction["faction_name"],
                        user=interaction.user,
                        details=f"✅ Faction `{faction['faction_name']}` confirmed as owner of `{flag_name}` on `{flag_map}`."
                    )
                else:
                    skipped += 1
                    await utils.log_faction_action(
                        guild,
                        action="Faction Sync Skipped",
                        faction_name=faction["faction_name"],
                        user=interaction.user,
                        details=f"⚠️ No flag found for `{faction['faction_name']}` — no changes made."
                    )

        # 🧾 Summary Embed
        embed = make_embed(
            "__Faction Sync Complete__",
            f"""
🗂️ **Guild:** {guild.name}
🔄 **Total Factions:** {total_factions}
✅ **Updated:** {updated}
⚙️ **Skipped:** {skipped}

🕓 Operation completed successfully.
            """,
            color=0x3498DB
        )

        embed.set_footer(
            text="Faction ↔ Flag Sync • DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionSync(bot))
