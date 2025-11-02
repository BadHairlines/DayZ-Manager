import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES
from cogs.utils import FLAGS, MAP_DATA, get_all_flags, set_flag, log_action


class Reassign(commands.Cog, BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete flag names."""
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    @app_commands.command(
        name="reassign",
        description="Move a flag from one role to another for a specific map."
    )
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    @admin_only()
    async def reassign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str,
        new_role: discord.Role
    ):
        """Transfers a flag from one role to another."""
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_name = MAP_DATA[map_key]["name"]

        # ✅ Fetch all current flags
        existing_flags = await get_all_flags(guild_id, map_key)
        db_flags = {r["flag"]: r for r in existing_flags}

        # 🚫 Check if this flag exists
        if flag not in db_flags:
            await interaction.response.send_message(
                f"❌ The **{flag}** flag doesn’t exist or hasn’t been initialized yet. Run `/setup` first.",
                ephemeral=True
            )
            return

        current_owner = db_flags[flag]["role_id"]
        if not current_owner:
            await interaction.response.send_message(
                f"⚠️ The **{flag}** flag isn’t currently assigned to any role.",
                ephemeral=True
            )
            return

        # 🚫 Prevent assigning to the same role
        if str(new_role.id) == current_owner:
            await interaction.response.send_message(
                f"⚠️ The **{flag}** flag is already assigned to {new_role.mention}.",
                ephemeral=True
            )
            return

        # 🚫 Check if the new role already owns another flag
        for record in existing_flags:
            if record["role_id"] == str(new_role.id):
                await interaction.response.send_message(
                    f"❌ {new_role.mention} already owns the **{record['flag']}** flag on **{map_name}**.",
                    ephemeral=True
                )
                return

        # ✅ Reassign in DB
        await set_flag(guild_id, map_key, flag, "❌", str(new_role.id))

        # ✅ Confirmation embed
        embed = self.make_embed(
            "**FLAG REASSIGNED**",
            f"🔁 The **{flag}** flag has been transferred from <@&{current_owner}> "
            f"to {new_role.mention} on **{map_name}**.",
            0x3498DB,
            "🔁",
            "Reassign Notification"
        )
        await interaction.response.send_message(embed=embed)

        # 🔁 Update live flag message
        await self.update_flag_message(guild, guild_id, map_key)

        # 🪵 Log the reassignment
        await log_action(
            guild,
            map_key,
            title="Flag Reassigned",
            description=(
                f"🔁 **{flag}** moved from <@&{current_owner}> → {new_role.mention}\n"
                f"👤 Changed by {interaction.user.mention} on **{map_name}**."
            ),
            color=0x3498DB
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reassign(bot))
