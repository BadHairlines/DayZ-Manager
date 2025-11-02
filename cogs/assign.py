import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs import utils
import asyncio


class Assign(commands.Cog, BaseCog):
    """Assign a flag to a faction or role."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="assign",
        description="Assign a flag to a specific faction or role for a chosen map."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Select which map this flag belongs to",
        flag="Enter the flag name to assign (e.g. Wolf, APA, NAPA)",
        role="Select the role or faction to assign the flag to"
    )
    async def assign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str,
        role: discord.Role
    ):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = normalize_map(selected_map)

        # ✅ Make sure DB is ready
        if utils.db_pool is None:
            return await interaction.followup.send("❌ Database not initialized. Please restart the bot.", ephemeral=True)

        # ✅ Validate flag exists
        if flag not in utils.FLAGS:
            return await interaction.followup.send(
                f"🚫 Invalid flag name. Must be one of:\n`{', '.join(utils.FLAGS)}`",
                ephemeral=True
            )

        # ✅ Check if already assigned
        flag_row = await utils.get_flag(guild_id, map_key, flag)
        if flag_row and flag_row["status"] == "❌":
            current_owner = flag_row["role_id"]
            return await interaction.followup.send(
                f"⚠️ Flag `{flag}` is already owned by <@&{current_owner}>.",
                ephemeral=True
            )

        # ✅ Assign flag in DB
        await utils.set_flag(guild_id, map_key, flag, "❌", str(role.id))

        # ✅ Try syncing with faction if exists
        faction = await utils.get_faction_by_flag(guild_id, flag)
        if not faction:
            async with utils.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE factions
                    SET claimed_flag=$1
                    WHERE guild_id=$2 AND role_id=$3 AND map=$4
                """, flag, guild_id, str(role.id), map_key)

        # ✅ Update flag display message
        try:
            await self.update_flag_message(guild, guild_id, map_key)
        except Exception as e:
            print(f"⚠️ Failed to update flag embed for {flag}: {e}")

        # ✅ Log action
        await utils.log_action(
            guild,
            map_key,
            title="Flag Assigned",
            description=f"🏴 Flag `{flag}` assigned to {role.mention} by {interaction.user.mention}.",
            color=0x2ECC71
        )

        # ✅ Faction log entry (if linked)
        await utils.log_faction_action(
            guild,
            action="Flag Assigned",
            faction_name=role.name,
            user=interaction.user,
            details=f"Flag `{flag}` claimed on map `{map_key.title()}`."
        )

        # ✅ Confirmation Embed
        embed = self.make_embed(
            title="✅ Flag Assigned",
            desc=(
                f"🏳️ **Flag:** `{flag}`\n"
                f"🗺️ **Map:** `{map_key.title()}`\n"
                f"🎭 **Assigned to:** {role.mention}\n"
                f"👤 **By:** {interaction.user.mention}"
            ),
            color=0x2ECC71,
            author_icon="🏴",
            author_name="Flag Assignment"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Assign(bot))
