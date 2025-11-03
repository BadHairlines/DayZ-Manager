import discord
from discord import app_commands
from discord.ext import commands

from dayz_manager.cogs.helpers.base_cog import BaseCog
from dayz_manager.cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from dayz_manager.cogs.utils.database import db_pool
from dayz_manager.cogs.utils.logging import log_action, log_faction_action
from dayz_manager.config import FLAGS as ALL_FLAGS

class Assign(commands.Cog, BaseCog):
    """Assign a flag to a faction or role."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="assign", description="Assign a flag to a specific faction or role for a chosen map.")
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(selected_map="Select which map this flag belongs to", flag="Enter the flag name to assign (e.g. Wolf, APA, NAPA)", role="Select the role or faction to assign the flag to")
    async def assign(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str, role: discord.Role):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = normalize_map(selected_map)

        if db_pool is None:
            return await interaction.followup.send("❌ Database not initialized. Please restart the bot.", ephemeral=True)

        if flag not in ALL_FLAGS:
            return await interaction.followup.send(f"🚫 Invalid flag name. Must be one of:\n`{', '.join(ALL_FLAGS)}`", ephemeral=True)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM flags WHERE guild_id=$1 AND map=$2 AND flag=$3;", guild_id, map_key, flag)

        if row and row["status"] == "❌":
            current_owner = row["role_id"]
            return await interaction.followup.send(f"⚠️ Flag `{flag}` is already owned by <@&{current_owner}>.", ephemeral=True)

        async with db_pool.acquire() as conn:
            await conn.execute("""                INSERT INTO flags (guild_id, map, flag, status, role_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, map, flag)
                DO UPDATE SET status = EXCLUDED.status, role_id = EXCLUDED.role_id;
            """, guild_id, map_key, flag, "❌", str(role.id))

            await conn.execute("""                UPDATE factions SET claimed_flag=$1 WHERE guild_id=$2 AND role_id=$3 AND map=$4
            """, flag, guild_id, str(role.id), map_key)

        try:
            await self.update_flag_message(guild, guild_id, map_key)
        except Exception as e:
            print(f"⚠️ Failed to update flag embed for {flag}: {e}")

        await log_action(guild, map_key, title="Flag Assigned", description=f"🏴 Flag `{flag}` assigned to {role.mention} by {interaction.user.mention}.", color=0x2ECC71)
        await log_faction_action(guild, action="Flag Assigned", faction_name=role.name, user=interaction.user, details=f"Flag `{flag}` claimed on map `{map_key.title()}`.")

        embed = self.make_embed(title="✅ Flag Assigned", desc=(
            f"🏳️ **Flag:** `{flag}`\n"
            f"🗺️ **Map:** `{map_key.title()}`\n"
            f"🎭 **Assigned to:** {role.mention}\n"
            f"👤 **By:** {interaction.user.mention}"
        ), color=0x2ECC71, author_icon="🏴", author_name="Flag Assignment")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Assign(bot))
