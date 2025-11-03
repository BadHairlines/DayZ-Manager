import discord
from discord import app_commands
from discord.ext import commands
from cogs import utils
from .faction_utils import make_embed, ensure_faction_table


class FactionSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================================
    # 🔄 /sync-factions
    # ============================================
    @app_commands.command(
        name="sync-factions",
        description="Synchronize factions and flags both ways — ensures ownership consistency."
    )
    @app_commands.describe(confirm="Confirm the synchronization operation.")
    async def sync_factions(self, interaction: discord.Interaction, confirm: bool):
        """Two-way sync: aligns factions ↔ flags data safely."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        # 🔒 Permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Only administrators can run this command.", ephemeral=True)

        if not confirm:
            return await interaction.followup.send("⚠️ Sync cancelled — confirmation not given.", ephemeral=True)

        guild = interaction.guild

        # 🧩 Ensure DB ready
        if utils.db_pool is None:
            return await interaction.followup.send("❌ Database not initialized. Restart the bot.", ephemeral=True)
        await ensure_faction_table()

        updated_flags = 0
        updated_factions = 0
        skipped = 0
        total_flags = 0
        total_factions = 0

        async with utils.db_pool.acquire() as conn:
            factions = await conn.fetch("SELECT * FROM factions WHERE guild_id=$1", str(guild.id))
            total_factions = len(factions)

            flags = await conn.fetch("SELECT map, flag, role_id FROM flags WHERE guild_id=$1", str(guild.id))
            total_flags = len(flags)

            # ✅ Normalize all map names for internal comparison
            for f in factions:
                f["map"] = f["map"].lower()
            for fl in flags:
                fl["map"] = fl["map"].lower()

            # Build lookup dictionaries
            role_to_flag = {r["role_id"]: (r["map"], r["flag"]) for r in flags if r["role_id"]}
            flag_to_role = {(r["map"], r["flag"]): r["role_id"] for r in flags if r["role_id"]}

            # ====================================
            # 🔁 Pass 1: Sync factions → flags
            # ====================================
            for faction in factions:
                role_id = faction["role_id"]
                map_key = faction["map"].lower()

                # Skip if no role exists
                if not guild.get_role(int(role_id)):
                    skipped += 1
                    continue

                # If faction’s role doesn’t own a flag, mark as skipped
                if role_id not in role_to_flag:
                    skipped += 1
                    continue

                # Otherwise verify ownership
                flag_map, flag_name = role_to_flag[role_id]

                # ✅ Normalize again for safety
                flag_map = flag_map.lower()

                # Log confirmation
                await utils.log_faction_action(
                    guild,
                    action="Faction Ownership Verified",
                    faction_name=faction["faction_name"],
                    user=interaction.user,
                    details=f"✅ `{faction['faction_name']}` confirmed as owning `{flag_name}` on `{flag_map}`."
                )
                updated_factions += 1

            # ====================================
            # 🔁 Pass 2: Sync flags → factions
            # ====================================
            for flag_record in flags:
                flag_map = flag_record["map"].lower()
                flag_name = flag_record["flag"]
                role_id = flag_record["role_id"]

                if not role_id:
                    continue  # unclaimed flag

                # Find a faction that has this role_id
                matching_faction = next((f for f in factions if f["role_id"] == role_id), None)

                if matching_faction:
                    # ✅ Already in sync
                    continue

                # ⚙️ A flag has a role with no faction record
                role = guild.get_role(int(role_id))
                if not role:
                    continue

                # Log the mismatch (flag owned by a non-faction role)
                await utils.log_faction_action(
                    guild,
                    action="Flag Ownership Unlinked",
                    faction_name=None,
                    user=interaction.user,
                    details=f"⚠️ Flag `{flag_name}` on `{flag_map}` is owned by `{role.name}` but no matching faction exists."
                )
                updated_flags += 1

            # ====================================
            # 🧹 Optional cleanup (unowned roles)
            # ====================================
            for faction in factions:
                role_id = faction["role_id"]
                if not guild.get_role(int(role_id)):
                    await utils.log_faction_action(
                        guild,
                        action="Faction Role Missing",
                        faction_name=faction["faction_name"],
                        user=interaction.user,
                        details=f"🚫 The role <@&{role_id}> for `{faction['faction_name']}` no longer exists in the guild."
                    )
                    skipped += 1

        # ====================================
        # 📊 Summary Report
        # ====================================
        embed = make_embed(
            "__Two-Way Faction Sync Complete__",
            f"""
🗂️ **Guild:** {guild.name}
🏳️ **Flags Checked:** {total_flags}
🎭 **Factions Checked:** {total_factions}

✅ **Factions Verified:** {updated_factions}
⚙️ **Flags Reviewed:** {updated_flags}
⏭️ **Skipped:** {skipped}

🕓 Sync completed successfully.
            """,
            color=0x3498DB
        )
        embed.set_footer(
            text="Faction ↔ Flag Two-Way Sync • DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FactionSync(bot))
